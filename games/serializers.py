from rest_framework import serializers

from games.models.bets import BetVariant
from games.models.matchs import Match
from games.models.payout import PayoutCategory
from games.models.rounds import Round
from games.models.wins import BiggestWin


########## МАКС ВЫИГРЫШ И ТОП ВЫИГРЫШЕЙ
class BiggestWinSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiggestWin
        fields = ["amount", "updated_at"]


class BetVariantTopSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="coupon.user.username")
    bet_amount = serializers.SerializerMethodField()

    class Meta:
        model = BetVariant
        fields = ["id", "username", "bet_amount", "win_amount", "win_multiplier"]

    def get_bet_amount(self, obj):
        return obj.coupon.bet_amount



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
    total_pool = serializers.SerializerMethodField()

    class Meta:
        model = Round
        fields = [
            "id",
            "status",
            "total_pool",
            "start_time",
            "selection_end_time",
            "matches",
            "jackpot",
        ]

    def get_jackpot(self, obj):
        from games.models.jackpot import Jackpot
        jp = Jackpot.objects.first()
        return jp.amount if jp else None

    def get_total_pool(self, obj):
        stats = getattr(obj, "stats", None)
        return stats.total_pool if stats else None


class BetVariantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="coupon.user.username")
    bet_amount = serializers.SerializerMethodField()

    class Meta:
        model = BetVariant
        fields = ["id", "username", "bet_amount", "win_amount", "win_multiplier"]

    def get_bet_amount(self, obj):
        try:
            return obj.coupon.amount_total / obj.coupon.num_variants
        except ZeroDivisionError:
            return 0


######### ИСТОРИЯ
class RoundHistorySerializer(serializers.ModelSerializer):
    biggest_win_x = serializers.DecimalField(source="stats.biggest_win_x", max_digits=6, decimal_places=2)

    class Meta:
        model = Round
        fields = ["id", "biggest_win_x"]
