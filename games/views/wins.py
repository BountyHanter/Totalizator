from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from games.models.bets import BetCoupon, BetVariant
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


class MyWinCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ищем все непросмотренные выигрышные купоны
        qs = BetCoupon.objects.filter(user=request.user, is_winner=True, is_seen=False)

        if not qs.exists():
            raise NotFound("Нет новых выигрышных купонов")

        # выбираем самый новый купон
        coupon = qs.order_by("-id").first()

        # помечаем все как просмотренные
        qs.update(is_seen=True)

        # готовим данные для фронта
        data = {
            "round_id": coupon.round_id,
            "coupon_id": coupon.id,
            "win_amount_total": str(coupon.win_amount_total),
        }

        return Response(data)
