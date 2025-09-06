from datetime import timedelta
from decimal import Decimal, DivisionByZero

from django.db.models import Sum, Max
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.wins import BiggestWin
from games.serializers import BiggestWinSerializer, BetVariantTopSerializer


class BiggestWinView(RetrieveAPIView):
    serializer_class = BiggestWinSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        # всегда возвращаем единственную запись
        return BiggestWin.objects.first()


class TopWinningVariantsView(ListAPIView):
    serializer_class = BetVariantTopSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        one_week_ago = timezone.now() - timedelta(days=7)

        return (
            BetVariant.objects
            .filter(coupon__created_at__gte=one_week_ago, win_amount__gt=0)
            .select_related("coupon__user", "coupon")
            .order_by("-win_amount", "-id")[:10]
        )



OUTCOME_TO_STR = {
    SelectedOutcome.Outcome.WIN1: "1",
    SelectedOutcome.Outcome.DRAW: "X",
    SelectedOutcome.Outcome.WIN2: "2",
}


class MyWinCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # все непросмотренные выигрышные купоны пользователя
        qs = BetCoupon.objects.filter(user=request.user, is_winner=True, is_seen=False)
        if not qs.exists():
            raise NotFound("Нет новых выигрышных купонов")

        # берём самый новый купон
        coupon = qs.order_by("-id").first()

        # сразу помечаем ВСЕ такие купоны как просмотренные
        qs.update(is_seen=True)

        # агрегаты по вариантам купона
        agg = (
            BetVariant.objects
            .filter(coupon=coupon)
            .aggregate(best_matched_count=Max("matched_count"))
        )
        best_matched_count = agg["best_matched_count"] or 0

        # собираем выборы по каждому матчу в рамках купона
        # (один раз на купон: без дублей вариантов)
        per_match = {}                    # match_id -> {"title": "...", "choices": set([...])}
        so_rows = (
            SelectedOutcome.objects
            .filter(variant__coupon=coupon)
            .select_related("match__team1", "match__team2")
            .values_list("match_id", "match__team1__name", "match__team2__name", "outcome")
        )
        for match_id, t1, t2, outcome_enum in so_rows:
            entry = per_match.get(match_id)
            if entry is None:
                entry = {"title": f"{t1} vs {t2}", "choices": set()}
                per_match[match_id] = entry
            entry["choices"].add(OUTCOME_TO_STR[outcome_enum])

        # преобразуем choices:set -> отсортированный список
        matches = {
            str(mid): {"title": data["title"], "choices": sorted(data["choices"])}
            for mid, data in per_match.items()
        }

        # деньги и коэффициент
        amount_total = (coupon.amount_total or Decimal("0")).quantize(Decimal("0.01"))
        win_total = (coupon.win_amount_total or Decimal("0")).quantize(Decimal("0.01"))
        try:
            coefficient = (win_total / amount_total).quantize(Decimal("0.01"))
        except (ZeroDivisionError, DivisionByZero):
            coefficient = Decimal("0.00")

        return Response({
            "round_id": coupon.round_id,
            "coupon_id": coupon.id,
            "amount_total": str(amount_total),
            "win_amount_total": str(win_total),
            "coefficient": str(coefficient),
            "best_matched_count": best_matched_count,
            "matches": matches,  # {"261": {"title": "...", "choices": ["1","X"]}, ...}
        })