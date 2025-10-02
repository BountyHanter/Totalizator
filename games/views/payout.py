from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from games.models.payout import PayoutScheme
from games.serializers import PayoutSchemeSerializer


class PayoutSchemeListView(ListAPIView):
    serializer_class = PayoutSchemeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            PayoutScheme.objects
            .filter(active=True)
            .select_related("color_scheme")  # чтобы не было N+1 запросов
            .order_by("id")
        )