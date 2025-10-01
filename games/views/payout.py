from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from games.models.payout import PayoutScheme
from games.serializers import PayoutSchemeSerializer


class PayoutSchemeListView(ListAPIView):
    serializer_class = PayoutSchemeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # отдаём только активные схемы
        return PayoutScheme.objects.filter(active=True).order_by("id")