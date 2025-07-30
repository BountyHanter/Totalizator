from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from games.models.bets import BetCoupon


@login_required
def user_bets_modal(request):
    user = request.user
    coupons = (
        BetCoupon.objects.filter(user=user)
        .select_related('round')
        .prefetch_related('variants__selected__match')
        .order_by('-created_at')
    )

    return render(request, "games/user_bets_modal.html", {"coupons": coupons})