from decimal import Decimal, DivisionByZero

from django.db import models
from django.contrib.auth import get_user_model

from games.models.matchs import Match
from games.models.rounds import Round

User = get_user_model()


class BetCoupon(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="coupons")
    amount_total = models.DecimalField(max_digits=10, decimal_places=2)
    num_variants = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Купон {self.id} (user={self.user_id}, round={self.round.id})"

    @property
    def bet_amount(self) -> Decimal:
        try:
            return self.amount_total / self.num_variants
        except (ZeroDivisionError, DivisionByZero):
            return Decimal("0.00")

    class Meta:
        indexes = [
            # Быстрые выборки последних купонов пользователя
            models.Index(fields=["user", "id"], name="coupon_user_id_idx"),
            # Для выборок купонов пользователя в конкретном раунде (MyVariantsInRoundView)
            models.Index(fields=["round", "user", "id"], name="coupon_round_user_id_idx"),
        ]


class BetVariant(models.Model):
    coupon = models.ForeignKey(BetCoupon, related_name="variants", on_delete=models.CASCADE)
    matched_count = models.PositiveSmallIntegerField(default=0)
    win_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    win_multiplier = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_win = models.BooleanField(default=False)

    def __str__(self):
        return f"Вариант купона {self.coupon.id} #{self.id} ({self.matched_count} совпадений)"

    def calculate_matched_count(self):
        outcome_mapping = {
            SelectedOutcome.Outcome.WIN1: Match.Outcome.WIN_1,
            SelectedOutcome.Outcome.DRAW: Match.Outcome.DRAW,
            SelectedOutcome.Outcome.WIN2: Match.Outcome.WIN_2,
        }
        matched = 0
        outcomes = self.selected.select_related('match').all()

        for outcome in outcomes:
            selected = outcome.outcome
            expected = outcome_mapping.get(selected)
            actual = outcome.match.result

            if actual and expected == actual:
                matched += 1
        return matched

    class Meta:
        indexes = [
            # Выплаты: фильтр по купонам раунда + отсечение по matched_count
            models.Index(fields=["coupon", "matched_count"], name="variant_coupon_matched_idx"),
            # «Последние варианты» по купону/пользователю (для order_by -id / limit)
            models.Index(fields=["coupon", "id"], name="variant_coupon_id_idx"),
        ]


class SelectedOutcome(models.Model):
    variant = models.ForeignKey(BetVariant, related_name='selected', on_delete=models.CASCADE)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)

    class Outcome(models.TextChoices):
        WIN1 = "win1", "Победа 1"
        DRAW = "draw", "Ничья"
        WIN2 = "win2", "Победа 2"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('match')  # обязательно!

    def is_correct(self) -> bool:
        """Вернёт True, если пользователь угадал исход."""
        return (
            (self.match.result == Match.Outcome.WIN_1 and self.outcome == self.Outcome.WIN1) or
            (self.match.result == Match.Outcome.DRAW  and self.outcome == self.Outcome.DRAW) or
            (self.match.result == Match.Outcome.WIN_2 and self.outcome == self.Outcome.WIN2)
        )
    def result_icon(self) -> str:
        return "✅" if self.is_correct() else "❌"

    outcome = models.CharField(max_length=5, choices=Outcome.choices)

    def __str__(self):
        return f"{self.match}: {self.outcome}"

    class Meta:
        constraints = [
            # Страховка от дублей: один матч на вариант — один раз
            models.UniqueConstraint(fields=["variant", "match"], name="uniq_variant_match"),
        ]