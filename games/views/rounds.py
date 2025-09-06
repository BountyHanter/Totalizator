from django.db.models import QuerySet, Prefetch
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import RetrieveAPIView, ListAPIView, get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.rounds import Round
from games.serializers import RoundSerializer, RoundHistorySerializer, BetVariantSerializer, RoundStatsSerializer, \
    UserBetVariantSerializer


class CurrentRoundView(RetrieveAPIView):
    serializer_class = RoundSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        obj = Round.objects.filter(
            status__in=[
                Round.Status.SELECTION,
                Round.Status.CALCULATION,
                Round.Status.PAYOUT
            ]
        ).order_by("-id").first()

        if not obj:
            raise NotFound("Нет активного раунда (selection/calculation/payout)")
        return obj


class CurrentRoundPoolView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        round_obj = (
            Round.objects
            .filter(
                status__in=[
                    Round.Status.SELECTION,
                    Round.Status.CALCULATION,
                    Round.Status.PAYOUT,
                ]
            )
            .order_by("-id")
            .values("id", "live_pool")   # ⚡ теперь берём из Round
            .first()
        )

        if not round_obj:
            raise NotFound("Нет активного раунда")

        return Response({
            "id": round_obj["id"],
            "live_pool": round_obj["live_pool"],   # возвращаем живой пул
        })


TRUTHY = {"1", "true", "t", "yes", "y", "on"}

class LastBetVariantsView(ListAPIView):
    serializer_class = BetVariantSerializer
    permission_classes = [AllowAny]

    DEFAULT_LIMIT = 5
    MAX_LIMIT = 100

    def _parse_limit(self):
        raw = self.request.query_params.get("limit", self.DEFAULT_LIMIT)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = self.DEFAULT_LIMIT
        return max(1, min(self.MAX_LIMIT, value))

    def _parse_is_me(self):
        raw = self.request.query_params.get("is_me", "false")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _current_round_id(self):
        obj = (
            Round.objects
            .filter(status__in=[Round.Status.SELECTION, Round.Status.CALCULATION, Round.Status.PAYOUT])
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
        )
        return obj  # может быть None

    def get_queryset(self):
        current_round_id = self._current_round_id()
        if current_round_id is None:
            return BetVariant.objects.none()

        qs = (
            BetVariant.objects
            .select_related("coupon__user", "coupon")
            .filter(coupon__round_id=current_round_id)
        )

        if self._parse_is_me():
            if not self.request.user.is_authenticated:
                raise PermissionDenied("Требуется авторизация для is_me=true")
            qs = qs.filter(coupon__user=self.request.user).order_by("-matched_count", "-id")
        else:
            qs = qs.order_by("-id")

        qs = qs[: self._parse_limit()]

        # нумерация 1..N для текущей выборки
        for idx, obj in enumerate(qs, start=1):
            obj.position = idx
        return qs

class RoundHistoryView(ListAPIView):
    serializer_class = RoundHistorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        limit = self.request.query_params.get("limit", 10)
        try:
            limit = max(1, min(50, int(limit)))  # ограничиваем до 50
        except ValueError:
            limit = 10

        qs = (
            Round.objects.filter(status=Round.Status.FINISHED)
            .select_related("stats")
            .order_by("-id")[:limit]
        )

        return qs


class RoundStatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        round_obj = get_object_or_404(Round.objects.select_related("stats"), pk=pk)

        if round_obj.status != Round.Status.FINISHED:
            return Response({"status": "Раунд не завершён"}, status=status.HTTP_403_FORBIDDEN)

        serializer = RoundStatsSerializer(round_obj.stats)
        return Response({
            "round": {"id": round_obj.id, "status": round_obj.status},
            **serializer.data
        })


class MyVariantsInRoundView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserBetVariantSerializer

    def get_queryset(self):
        round_id = self.kwargs["pk"]
        try:
            round_obj = Round.objects.only("id").get(pk=round_id)
        except Round.DoesNotExist:
            raise NotFound("Раунд не найден")

        # Все варианты текущего пользователя в этом раунде
        qs = (
            BetVariant.objects
            .filter(coupon__round=round_obj, coupon__user=self.request.user)
            .select_related("coupon")  # для bet_amount
            .prefetch_related(
                Prefetch(
                    "selected",
                    queryset=SelectedOutcome.objects.select_related(
                        "match", "match__team1", "match__team2"
                    ).only(
                        "id", "outcome",
                        "match__id", "match__result",
                        "match__team1__name", "match__team2__name",
                    )
                )
            )
            .only(
                "id", "matched_count", "win_amount", "win_multiplier", "is_win",
                "coupon__amount_total", "coupon__num_variants",
            )
        )
        return qs