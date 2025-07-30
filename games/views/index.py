from decimal import Decimal

from django.shortcuts import render

from games.models.jackpot import Jackpot
from games.models.payout import PayoutCategory
from games.models.rounds import Round


def index(request):
    jackpot = Jackpot.objects.first()
    try:
        round = Round.objects.filter(
            status__in=[
                Round.Status.SELECTION,
                Round.Status.CALCULATION,
                Round.Status.PAYOUT,
            ]
        ).order_by('start_time').last()
    except Round.DoesNotExist:
        round = None
    matches = round.matches.select_related('team1', 'team2') if round else []

    payout_categories = PayoutCategory.objects.filter(active=True).order_by("order")

    outcome_choices = [("1", "П1"), ("X", "Х"), ("2", "П2")]

    return render(request, "games/index.html", {
        "jackpot": jackpot,
        "round": round,
        "total_pool": round.total_pool * Decimal("0.95") if round else None,
        "matches": matches,
        "payout_categories": payout_categories,
        "outcome_choices": outcome_choices,
        "start_timestamp": int(round.start_time.timestamp()) if round else None,
    })
