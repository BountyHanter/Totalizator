from itertools import product
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.jackpot import Jackpot
from games.models.payout import PayoutCategory
from games.models.rounds import Round

OUTCOME_MAP = {
    "1": SelectedOutcome.Outcome.WIN1,
    "X": SelectedOutcome.Outcome.DRAW,
    "2": SelectedOutcome.Outcome.WIN2,
}

@require_http_methods(["GET", "POST"])
def bet(request):
    user = request.user
    jackpot = Jackpot.objects.first()
    round = Round.objects.filter(status=Round.Status.SELECTION).first()
    matches = round.matches.select_related('team1', 'team2') if round else []
    payout_categories = PayoutCategory.objects.filter(active=True).order_by("order")

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")

        try:
            stake_per_variant = Decimal(request.POST.get("amount_total", "0"))
        except:
            stake_per_variant = Decimal("0")

        if stake_per_variant <= 0:
            messages.error(request, "Сумма ставки должна быть положительной.")
            return redirect("index")

        # Собрать выборы по матчам
        match_outcomes = {}
        for match in matches:
            values = request.POST.getlist(f"outcome_{match.id}")
            valid = [v for v in values if v in OUTCOME_MAP]
            if valid:
                match_outcomes[match.id] = valid

        if len(match_outcomes) != 10:
            messages.error(request, "Необходимо выбрать хотя бы один исход в каждом из 10 матчей.")
            return redirect("index")

        # Построить варианты
        grouped = [
            [(match_id, outcome) for outcome in outcomes]
            for match_id, outcomes in match_outcomes.items()
        ]
        combinations = list(product(*grouped))

        if not combinations:
            messages.error(request, "Не удалось сформировать варианты ставок.")
            return redirect("index")

        total_amount = stake_per_variant * len(combinations)

        if user.balance_cached < total_amount:
            messages.error(request, "Недостаточно средств.")
            return redirect("index")

        # Создать купон
        coupon = BetCoupon.objects.create(
            user=user,
            round=round,
            amount_total=total_amount,
            num_variants=len(combinations)
        )

        # Подготовка вариантов
        variant_objs = [BetVariant(coupon=coupon) for _ in combinations]
        BetVariant.objects.bulk_create(variant_objs)

        # Обновить список с id (если нужно), но Django 4+ с PostgreSQL сам подставит id
        variant_objs = list(BetVariant.objects.filter(coupon=coupon).order_by("id"))

        # Подготовка исходов
        outcome_objs = []
        for variant, combo in zip(variant_objs, combinations):
            for match_id, outcome_raw in combo:
                outcome_objs.append(SelectedOutcome(
                    variant=variant,
                    match_id=match_id,
                    outcome=OUTCOME_MAP[outcome_raw]
                ))

        SelectedOutcome.objects.bulk_create(outcome_objs)

        user.balance_cached -= total_amount
        user.save(update_fields=["balance_cached"])

        messages.success(request, f"Ставка успешно сделана! Кол-во вариантов: {len(combinations)}.")
        return redirect("index")

    return render(request, "games/index.html", {
        "jackpot": jackpot,
        "round": round,
        "matches": matches,
        "payout_categories": payout_categories,
    })
