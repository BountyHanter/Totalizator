from decimal import Decimal, DivisionByZero

from django.http import HttpResponseBadRequest, JsonResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.db.models import Count, Sum

from games.models.bets import BetVariant, BetCoupon
from games.models.payout import PayoutCategory
from games.models.rounds import Round


def stats_view(request):
    date_filter = request.GET.get("date")
    qs = Round.objects.filter(status=Round.Status.FINISHED)
    if date_filter:
        d = parse_date(date_filter)
        if d:
            qs = qs.filter(start_time__date=d)

    rounds = qs.annotate(match_count=Count("matches"))

    # --- Считаем, сколько юзер поставил/выиграл по каждому раунду ---
    user_staked = {}
    user_won = {}
    if request.user.is_authenticated:
        # Ставки
        stakes = (
            BetCoupon.objects
            .filter(user=request.user, round__in=rounds)
            .values("round_id")
            .annotate(total=Sum("amount_total"))
        )
        for s in stakes:
            user_staked[s["round_id"]] = s["total"] or Decimal("0")
        # Выигрыши
        wins = (
            BetVariant.objects
            .filter(coupon__user=request.user, coupon__round__in=rounds, is_win=True)
            .values("coupon__round_id")
            .annotate(total=Sum("win_amount"))
        )
        for w in wins:
            user_won[w["coupon__round_id"]] = w["total"] or Decimal("0")
    # ---------------------------------------------------------------

    # Проценты по категориям (для round_payouts, max_wins и т.д.)
    pct = { str(c.matched_count): c.percent for c in PayoutCategory.objects.filter(active=True) }

    # round_payouts и max_wins можно собирать здесь, но т.к. они подгружаются лениво —
    # передавать их не нужно в stats_view.

    return render(request, "games/stats.html", {
        "rounds":        rounds,
        "selected_date": date_filter,
        "user_staked":   user_staked,
        "user_won":      user_won,
    })


def stats_round_partial(request, round_id):
    if not request.user.is_authenticated:
        raise Http404()
    r = get_object_or_404(Round, pk=round_id, status=Round.Status.FINISHED)

    # Проценты по категориям
    payout_percent = {
        str(c.matched_count): c.percent
        for c in PayoutCategory.objects.filter(active=True)
    }

    # Выплаты по категориям
    payouts = {}
    if hasattr(r, "stats"):
        pool = r.stats.payout_pool
        for cat, pct in payout_percent.items():
            payouts[cat] = round(pool * pct / Decimal("100"), 2)

    # Топ-показатели
    top_sum = top_sum_x = top_x = top_x_sum = None
    if hasattr(r, "stats"):
        variants = BetVariant.objects.select_related("coupon").filter(
            coupon__round=r, is_win=True
        )
        for v in variants:
            try:
                bet = v.coupon.amount_total / v.coupon.num_variants
                if not bet:
                    continue
                x = v.win_amount / bet
            except (ZeroDivisionError, DivisionByZero):
                continue
            if top_sum is None or v.win_amount > top_sum:
                top_sum, top_sum_x = v.win_amount, x
            if top_x is None or x > top_x:
                top_x, top_x_sum = x, v.win_amount

    max_data = {
        "best_win":   round(top_sum,   2) if top_sum   else None,
        "best_win_x": round(top_sum_x, 2) if top_sum_x else None,
        "best_x":     round(top_x,     2) if top_x     else None,
        "best_x_win": round(top_x_sum, 2) if top_x_sum else None,
    }

    winners = r.stats.winners_by_category if hasattr(r, "stats") else {}

    # Подсчёт «ставок»/«выигрыша» юзера в этом раунде (чтобы показать их в модалке)
    staked = BetCoupon.objects.filter(user=request.user, round=r).aggregate(s=Sum("amount_total"))["s"] or Decimal("0")
    won    = BetVariant.objects.filter(coupon__user=request.user, coupon__round=r, is_win=True).aggregate(s=Sum("win_amount"))["s"] or Decimal("0")

    html = render_to_string("games/stats_modal_content.html", {
        "round":        r,
        "payouts":      payouts,
        "max_data":     max_data,
        "winners":      winners,
        "total_staked": staked,
        "total_won":    won,
    }, request=request)

    # Возвращаем чистый HTML, а не JSON
    return HttpResponse(html)


def user_variants_partial(request, round_id):
    if not request.user.is_authenticated:
        raise Http404()
    coupons = BetCoupon.objects.filter(
        user=request.user, round_id=round_id
    ).prefetch_related("variants__selected__match")
    html = render_to_string(
        "games/user_variants_partial.html",
        {"coupons": coupons},
        request=request
    )
    return HttpResponse(html)
