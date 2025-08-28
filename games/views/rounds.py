from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from games.models.bets import BetCoupon, BetVariant
from games.models.rounds import Round
from games.serializers import RoundSerializer, RoundHistorySerializer, BetVariantSerializer


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
        # TODO: попробовать достать значение из Redis
        # pool = redis_client.get("current_round_pool")
        # if pool:
        #     return Response({"total_pool": pool})

        # если нет в Redis — достаём из БД
        round_obj = Round.objects.filter(
            status__in=[
                Round.Status.SELECTION,
                Round.Status.CALCULATION,
                Round.Status.PAYOUT,
            ]
        ).order_by("-id").values("id", "total_pool").first()

        if not round_obj:
            raise NotFound("Нет активного раунда")

        # TODO: сохранить в Redis на будущее
        # redis_client.set("current_round_pool", round_obj["total_pool"])

        return Response(round_obj)


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

    def get_queryset(self):
        qs = (
            BetVariant.objects
            .select_related("coupon__user", "coupon")
            .order_by("-id")
        )

        if self._parse_is_me():
            if not self.request.user.is_authenticated:
                raise PermissionDenied("Требуется авторизация для is_me=true")
            qs = qs.filter(coupon__user=self.request.user)

        return qs[: self._parse_limit()]


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
            .only("id", "stats__biggest_win_x")
            .order_by("-id")[:limit]
        )

        return qs