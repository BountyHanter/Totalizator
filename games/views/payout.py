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
            .prefetch_related("color_intervals")  # важно для ForeignKey (много)
            .order_by("id")
        )
