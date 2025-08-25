from itertools import product
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, NotFound

from games.models.rounds import Round
from games.models.bets import BetCoupon, BetVariant, SelectedOutcome


OUTCOME_MAP = {
    "1": SelectedOutcome.Outcome.WIN1,
    "X": SelectedOutcome.Outcome.DRAW,
    "2": SelectedOutcome.Outcome.WIN2,
}


class PlaceBetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # входные данные
        round_id = request.data.get("round_id")
        stake_per_variant = request.data.get("stake_per_variant")
        predictions = request.data.get("predictions")

        # базовые проверки
        if not round_id or not stake_per_variant or not predictions:
            raise ValidationError("Не все обязательные поля переданы.")

        try:
            stake_per_variant = Decimal(stake_per_variant)
        except:
            raise ValidationError("Ставка должна быть числом.")

        if stake_per_variant <= 0:
            raise ValidationError("Ставка на вариант должна быть положительной.")

        # проверяем раунд
        try:
            round_obj = Round.objects.get(id=round_id, status=Round.Status.SELECTION)
        except Round.DoesNotExist:
            raise ValidationError("Нет доступного раунда для ставок.")

        # проверяем количество матчей
        if len(predictions) != 10:
            raise ValidationError("Необходимо выбрать исходы во всех 10 матчах.")

        # строим комбинации
        grouped = []
        for match_id, outcomes in predictions.items():
            if not outcomes:
                raise ValidationError(f"Матч {match_id}: нужно выбрать хотя бы один исход.")
            valid = [o for o in outcomes if o in OUTCOME_MAP]
            if not valid:
                raise ValidationError(f"Матч {match_id}: некорректные исходы.")
            grouped.append([(int(match_id), outcome) for outcome in valid])

        combinations = list(product(*grouped))
        if not combinations:
            raise ValidationError("Не удалось сформировать варианты ставок.")

        num_variants = len(combinations)
        total_amount = stake_per_variant * num_variants

        # проверяем баланс
        if user.balance_cached < total_amount:
            raise ValidationError("Недостаточно средств для ставки.")

        # создаём купон
        coupon = BetCoupon.objects.create(
            user=user,
            round=round_obj,
            amount_total=total_amount,
            num_variants=num_variants
        )

        # создаём варианты
        variant_objs = [BetVariant(coupon=coupon) for _ in combinations]
        BetVariant.objects.bulk_create(variant_objs)

        # получаем созданные варианты
        variant_objs = list(BetVariant.objects.filter(coupon=coupon).order_by("id"))

        # создаём исходы
        outcome_objs = []
        for variant, combo in zip(variant_objs, combinations):
            for match_id, outcome_raw in combo:
                outcome_objs.append(SelectedOutcome(
                    variant=variant,
                    match_id=match_id,
                    outcome=OUTCOME_MAP[outcome_raw]
                ))
        SelectedOutcome.objects.bulk_create(outcome_objs)

        # списываем баланс
        user.balance_cached -= total_amount
        user.save(update_fields=["balance_cached"])

        return Response({
            "status": "ok",
            "balance_left": str(user.balance_cached)
        })
