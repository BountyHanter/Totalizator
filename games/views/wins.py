from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from games.models.bets import BetCoupon
from games.models.wins import BiggestWin
from games.serializers import BiggestWinSerializer, BetCouponTopSerializer


class BiggestWinView(RetrieveAPIView):
    serializer_class = BiggestWinSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        # всегда возвращаем единственную запись
        return BiggestWin.objects.first()


class TopWinningCouponsView(ListAPIView):
    serializer_class = BetCouponTopSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        # TODO: достать из Redis
        # cached = redis_client.get("top_wins_week")
        # if cached:
        #     return Response(json.loads(cached))

        one_week_ago = timezone.now() - timedelta(days=7)

        qs = (
            BetCoupon.objects
            .filter(created_at__gte=one_week_ago)
            .annotate(total_win=Sum("variants__win_amount"))
            .filter(total_win__gt=0)
            .select_related("user")
            .order_by("-total_win", "-created_at")[:10]
        )

        serializer = self.get_serializer(qs, many=True)
        data = serializer.data

        # TODO: сохранить в Redis на 1 час, например
        # redis_client.set("top_wins_week", json.dumps(data), ex=3600)

        return Response(data)