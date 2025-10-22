from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from games.models.fanfool import FanPool


class FanPoolAmountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        pool = FanPool.get_solo()  # берём единственный объект
        return Response({"amount": pool.amount})