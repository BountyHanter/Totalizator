from itertools import product, islice
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from games.models.payout import PayoutScheme
from games.models.rounds import Round
from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from users.models.fanfool import FanPool

OUTCOME_MAP = {
    "1": SelectedOutcome.Outcome.WIN1,
    "X": SelectedOutcome.Outcome.DRAW,
    "2": SelectedOutcome.Outcome.WIN2,
}

def iter_combinations(grouped, batch_size=1000):
    """Лениво выдаёт комбинации батчами, чтобы не держать всё в памяти."""
    it = product(*grouped)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            break
        yield batch

class PlaceBetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # входные данные
        round_id = request.data.get("round_id")
        stake_per_variant = request.data.get("stake_per_variant")
        predictions = request.data.get("predictions")
        payout_scheme_id = request.data.get("payout_scheme_id")

        # базовые проверки
        if not round_id or not stake_per_variant or not predictions or not payout_scheme_id:
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

        # проверяем схему выплат
        try:
            scheme = PayoutScheme.objects.get(id=payout_scheme_id, active=True)
        except PayoutScheme.DoesNotExist:
            raise ValidationError("Указанная схема выплат не найдена или не активна.")

        # проверяем количество матчей
        if len(predictions) != 10:
            raise ValidationError("Необходимо выбрать исходы во всех 10 матчах.")

        # Собираем матчи
        valid_matches = set(round_obj.matches.values_list("id", flat=True))

        for match_id, outcomes in predictions.items():
            try:
                match_id = int(match_id)
            except ValueError:
                raise ValidationError(f"Некорректный match_id: {match_id}")

            if match_id not in valid_matches:
                raise ValidationError(f"Матч {match_id} не относится к этому раунду.")

        # строим комбинации
        grouped = []
        for match_id, outcomes in predictions.items():
            if not outcomes:
                raise ValidationError(f"Матч {match_id}: нужно выбрать хотя бы один исход.")

            seen = set()
            valid = []
            for o in outcomes:
                if o in OUTCOME_MAP and o not in seen:
                    valid.append(o)
                    seen.add(o)

            if not valid:
                raise ValidationError(f"Матч {match_id}: некорректные исходы.")
            grouped.append([(int(match_id), outcome) for outcome in valid])

        # Считаем кол-во комбинаций (через len(product) нельзя — используем произведение длин)
        num_variants = 1
        for g in grouped:
            num_variants *= len(g)

        if num_variants > 10000:
            raise ValidationError("Превышено максимальное число вариантов (10 000). Уточните выбор.")

        total_amount = stake_per_variant * num_variants

        # проверяем баланс
        if user.balance_cached < total_amount:
            raise ValidationError("Недостаточно средств для ставки.")

        with transaction.atomic():
            # создаём купон
            coupon = BetCoupon.objects.create(
                user=user,
                round=round_obj,
                payout_scheme=scheme,
                amount_total=total_amount,
                num_variants=num_variants
            )

            # Генерация и вставка партиями
            for combo_batch in iter_combinations(grouped, batch_size=1000):
                variant_batch = [BetVariant(coupon=coupon) for _ in combo_batch]
                created_variants = BetVariant.objects.bulk_create(
                    variant_batch,
                    batch_size=1000,
                    returning=True,  # type: ignore[arg-type]
                )

                outcome_objs = []
                for variant, combo in zip(created_variants, combo_batch):
                    for match_id, outcome_raw in combo:
                        outcome_objs.append(SelectedOutcome(
                            variant=variant,
                            match_id=match_id,
                            outcome=OUTCOME_MAP[outcome_raw],
                        ))

                SelectedOutcome.objects.bulk_create(outcome_objs, batch_size=10000)

            # списываем баланс атомарно
            updated_rows = type(user).objects.filter(
                id=user.id,
                balance_cached__gte=total_amount
            ).update(balance_cached=F("balance_cached") - total_amount)

            if updated_rows != 1:
                raise ValidationError("Недостаточно средств или баланс изменился.")

            # обновляем пул фанатов
            pool = FanPool.objects.first()
            if pool:
                contribution = (total_amount * pool.percent / 100).quantize(Decimal("0.01"))
                FanPool.objects.filter(id=pool.id).update(
                    amount=F("amount") + contribution,
                    updated_at=timezone.now(),
                )

        # обновляем данные пользователя в памяти
        user.refresh_from_db(fields=["balance_cached"])

        return Response({
            "status": "ok",
            "balance_left": str(user.balance_cached)
        })
