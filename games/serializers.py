from rest_framework import serializers

from games.models.bets import BetVariant, SelectedOutcome
from games.models.matchs import Match
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats
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

    class Meta:
        model = Round
        fields = [
            "id",
            "status",
            "live_pool",
            "start_time",
            "selection_end_time",
            "matches",
            "jackpot",
        ]

    def get_jackpot(self, obj):
        from games.models.jackpot import Jackpot
        jp = Jackpot.objects.first()
        return jp.amount if jp else None


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
    biggest_win_x = serializers.SerializerMethodField()

    class Meta:
        model = Round
        fields = ["id", "biggest_win_x"]

    def get_biggest_win_x(self, obj):
        # достаём x из best_multiplier или 0
        stats = getattr(obj, "stats", None)
        if stats and isinstance(stats.best_multiplier, dict):
            return stats.best_multiplier.get("x", 0)
        return 0


class RoundStatsSerializer(serializers.ModelSerializer):
    totals = serializers.SerializerMethodField()
    extremes = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = RoundStats
        fields = ["totals", "extremes", "categories"]

    def get_totals(self, obj: RoundStats):
        return {
            "total_pool": obj.total_pool,
            "payout_pool": obj.payout_pool,
            "jackpot_before": obj.jackpot_before,
            "jackpot_after": obj.jackpot_after,
            "total_win": obj.total_win,
        }

    def get_extremes(self, obj: RoundStats):
        return {
            "biggest_win": obj.biggest_win,       # {"sum": "...", "x": "..."}
            "best_multiplier": obj.best_multiplier, # {"x": "...", "sum": "..."}
        }

    def get_categories(self, obj: RoundStats):
        return {
            "winners": obj.count_winners_by_category,
            "payouts": obj.payout_by_category,
        }




RESULT_MAPPING = {
    Match.Outcome.WIN_1: "win1",
    Match.Outcome.DRAW:  "draw",
    Match.Outcome.WIN_2: "win2",
    None: None,
}


class SelectedOutcomeSerializer(serializers.ModelSerializer):
    match_id = serializers.IntegerField(source="match.id", read_only=True)
    team1 = serializers.CharField(source="match.team1.name", read_only=True)
    team2 = serializers.CharField(source="match.team2.name", read_only=True)
    user_pick = serializers.CharField(source="outcome", read_only=True)
    result = serializers.SerializerMethodField()
    correct = serializers.SerializerMethodField()

    class Meta:
        model = SelectedOutcome
        fields = ("match_id", "team1", "team2", "user_pick", "result", "correct")

    def get_result(self, obj: SelectedOutcome):
        return RESULT_MAPPING.get(obj.match.result)

    def get_correct(self, obj: SelectedOutcome):
        res = RESULT_MAPPING.get(obj.match.result)
        return (res is not None) and (res == obj.outcome)


class UserBetVariantSerializer(serializers.ModelSerializer):
    bet_amount = serializers.SerializerMethodField()
    selections = SelectedOutcomeSerializer(source="selected", many=True, read_only=True)

    class Meta:
        model = BetVariant
        fields = (
            "id",
            "bet_amount",
            "matched_count",
            "win_amount",
            "win_multiplier",
            "is_win",
            "selections",
        )

    def get_bet_amount(self, obj: BetVariant):
        # ставка на вариант из купона (amount_total / num_variants)
        # свойство уже есть в BetCoupon.bet_amount
        return obj.coupon.bet_amount