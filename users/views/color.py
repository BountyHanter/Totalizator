from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from users.models import ColorInterval


class ColorIntervalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorInterval
        fields = ["start_value", "end_value", "background_color", "border_color"]


class ColorIntervalListView(ListAPIView):
    queryset = ColorInterval.objects.all().order_by("start_value")
    serializer_class = ColorIntervalSerializer
    permission_classes = [AllowAny]