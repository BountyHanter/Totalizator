from itertools import product
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from games.models.payout import PayoutScheme
from games.models.rounds import Round
from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.fanfool import FanPool
from teams.models.teams import Team

OUTCOME_MAP = {
    "1": SelectedOutcome.Outcome.WIN1,
    "X": SelectedOutcome.Outcome.DRAW,
    "2": SelectedOutcome.Outcome.WIN2,
}

FANPOINTS_PERCENT = Decimal("1.00")

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
        except Exception:
            raise ValidationError("Ставка должна быть числом.")

        if stake_per_variant <= 0:
            raise ValidationError("Ставка на вариант должна быть положительной.")

        # Поддержка очень маленьких ставок (например 0.1, 0.01, 0.001, ...).
        # Округляем до 4 знаков после запятой для стабильности вычислений.
        stake_per_variant = stake_per_variant.quantize(Decimal("0.0001"))

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

        # допустимые матчи
        valid_matches = set(round_obj.matches.values_list("id", flat=True))
        for match_id, outcomes in predictions.items():
            try:
                match_id = int(match_id)
            except ValueError:
                raise ValidationError(f"Некорректный match_id: {match_id}")
            if match_id not in valid_matches:
                raise ValidationError(f"Матч {match_id} не относится к этому раунду.")

        # группируем исходы
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

        # считаем количество комбинаций
        num_variants = 1
        for g in grouped:
            num_variants *= len(g)
        if num_variants > 10000:
            raise ValidationError("Превышено максимальное число вариантов (10 000).")

        total_amount = (stake_per_variant * num_variants).quantize(Decimal("0.0001"))
        if user.balance_cached < total_amount:
            raise ValidationError("Недостаточно средств для ставки.")

        # основная транзакция
        with transaction.atomic():
            coupon = BetCoupon.objects.create(
                user=user,
                round=round_obj,
                payout_scheme=scheme,
                amount_total=total_amount,
                num_variants=num_variants,
            )

            # создаём все варианты одной пачкой
            combinations = list(product(*grouped))
            variants = [BetVariant(coupon=coupon) for _ in combinations]
            BetVariant.objects.bulk_create(variants, batch_size=1000)

            # получаем созданные варианты по порядку
            created_variants = list(BetVariant.objects.filter(coupon=coupon).order_by("id"))

            # создаём все исходы
            outcomes = []
            for variant, combo in zip(created_variants, combinations):
                for match_id, outcome_raw in combo:
                    outcomes.append(SelectedOutcome(
                        variant=variant,
                        match_id=match_id,
                        outcome=OUTCOME_MAP[outcome_raw],
                    ))

            # массовая вставка исходов
            SelectedOutcome.objects.bulk_create(outcomes, batch_size=30000)

            # списываем баланс атомарно
            updated_rows = type(user).objects.filter(
                id=user.id,
                balance_cached__gte=total_amount
            ).update(balance_cached=F("balance_cached") - total_amount)
            if updated_rows != 1:
                raise ValidationError("Недостаточно средств или баланс изменился.")

            # обновляем фан-пул
            pool = FanPool.get_solo()
            if pool:
                contribution = (total_amount * pool.percent / 100).quantize(Decimal("0.0001"))
                FanPool.objects.filter(id=pool.id).update(
                    amount=F("amount") + contribution,
                )

            # Добавляем фанпоинтс если команда участвует
            favorite_team = user.favorite_team
            if favorite_team:
                team_plays = round_obj.matches.filter(
                    Q(team1=favorite_team) | Q(team2=favorite_team)
                ).exists()
                if team_plays:
                    points = (total_amount * FANPOINTS_PERCENT / 100).quantize(Decimal("0.01"))
                    Team.objects.filter(id=favorite_team.id).update(fanpoints=F("fanpoints") + points)

        # обновляем баланс в объекте пользователя
        user.refresh_from_db(fields=["balance_cached"])

        return Response({
            "status": "ok",
            "balance_left": str(user.balance_cached)
        })
