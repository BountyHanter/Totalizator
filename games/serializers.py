from rest_framework import serializers

from games.models.bets import BetCoupon
from games.models.matchs import Match
from games.models.payout import PayoutCategory
from games.models.rounds import Round
from games.models.wins import BiggestWin


########## МАКС ВЫИГРЫШ И ТОП ВЫИГРЫШЕЙ
class BiggestWinSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiggestWin
        fields = ["amount", "updated_at"]


class BetCouponTopSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    total_win = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = BetCoupon
        fields = ["id", "username", "total_win", "created_at"]


######### ПРОЦЕНТ ВЫПЛАТ
class PayoutCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutCategory
        fields = ["matched_count", "percent", "active"]


######### ТЕКУЩИЙ РАУНД
class MatchSerializer(serializers.ModelSerializer):
    team1 = serializers.StringRelatedField()
    team2 = serializers.StringRelatedField()

    class Meta:
        model = Match
        fields = ["id", "team1", "team2"]


class RoundSerializer(serializers.ModelSerializer):
    matches = MatchSerializer(many=True, read_only=True)
    jackpot = serializers.SerializerMethodField()

    class Meta:
        model = Round
        fields = ["id", "status", "total_pool", "start_time", "end_time", "matches", "jackpot"]

    def get_jackpot(self, obj):
        from games.models.jackpot import Jackpot  # импорт внутри, чтобы избежать циклов
        jackpot = Jackpot.objects.first()
        return jackpot.amount if jackpot else None


class BetCouponShortSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")

    class Meta:
        model = BetCoupon
        fields = ["id", "amount_total", "username"]


######### ИСТОРИЯ
class RoundHistorySerializer(serializers.ModelSerializer):
    biggest_win_x = serializers.DecimalField(source="stats.biggest_win_x", max_digits=6, decimal_places=2)

    class Meta:
        model = Round
        fields = ["id", "biggest_win_x"]
