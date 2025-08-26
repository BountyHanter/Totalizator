from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from games.models.payout import PayoutCategory
from games.serializers import PayoutCategorySerializer


class PayoutCategoryListView(ListAPIView):
    serializer_class = PayoutCategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # отдаем только активные
        return PayoutCategory.objects.filter(active=True).order_by("id")