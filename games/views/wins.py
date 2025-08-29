from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

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