from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from games.models.bets import BetVariant, BetCoupon
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats
from games.models.wins import BiggestWin


Q2 = Decimal("0.01")  # квант для округления до копеек


@transaction.atomic
def process_payouts(round_obj: Round):
    """
    Расчёт выплат по новой схеме:
    - Берём ставку на вариант = amount_total / num_variants
    - Находим коэффициент по matched_count в PayoutCategory
    - Выигрыш = ставка * коэффициент
    - Заполняем win_amount, win_multiplier, is_win
    - Обновляем купоны, балансы, RoundStats и BiggestWin
    """
    round_obj.refresh_from_db()
    round_obj.status = Round.Status.PAYOUT
    round_obj.save(update_fields=["status"])

    # активные коэффициенты
    coeff_by_count = {
        c.matched_count: c.coefficient
        for c in PayoutCategory.objects.filter(active=True).only("matched_count", "coefficient")
    }

    # подготовка под статистику
    count_winners_by_category = {str(k): 0 for k in coeff_by_count.keys()}
    payout_by_category_dec = {str(k): Decimal("0.00") for k in coeff_by_count.keys()}

    # варианты раунда
    variants = list(
        BetVariant.objects
        .filter(coupon__round=round_obj)
        .select_related("coupon", "coupon__user")
        .only(
            "id", "matched_count", "win_amount", "win_multiplier", "is_win",
            "coupon__id", "coupon__amount_total", "coupon__num_variants",
            "coupon__user__id",
        )
    )
    if not variants:
        _finalize_round_with_stats(
            round_obj=round_obj,
            total_win=Decimal("0.00"),
            count_winners_by_category=count_winners_by_category,
            payout_by_category_dec=payout_by_category_dec,
            best_multiplier={"x": 0.00, "sum": 0.00},
            biggest_win={"sum": 0.00, "x": 0.00},
        )
        return

    bet_amount_cache: dict[int, Decimal] = {}
    total_win = Decimal("0.00")
    best_multiplier = {"x": 0.00, "sum": 0.00}
    biggest_win = {"sum": 0.00, "x": 0.00}

    coupon_total_win: dict[int, Decimal] = defaultdict(Decimal)
    user_balance_delta: dict[int, Decimal] = defaultdict(Decimal)

    # рекорд за этот раунд
    round_max_variant_win = Decimal("0.00")

    for v in variants:
        # ставка на вариант
        cid = v.coupon_id
        bet_amount = bet_amount_cache.get(cid)
        if bet_amount is None:
            try:
                bet_amount = (v.coupon.amount_total / v.coupon.num_variants).quantize(Q2)
            except Exception:
                bet_amount = Decimal("0.00")
            bet_amount_cache[cid] = bet_amount

        coeff = coeff_by_count.get(v.matched_count)
        if coeff:
            v.win_multiplier = coeff
            v.win_amount = (bet_amount * coeff).quantize(Q2, rounding=ROUND_HALF_UP)
            v.is_win = v.win_amount > 0

            key = str(v.matched_count)
            if key in count_winners_by_category:
                count_winners_by_category[key] += 1
                payout_by_category_dec[key] = (payout_by_category_dec[key] + v.win_amount).quantize(Q2)

            total_win = (total_win + v.win_amount).quantize(Q2)
            coupon_total_win[cid] = (coupon_total_win[cid] + v.win_amount).quantize(Q2)
            user_balance_delta[v.coupon.user_id] = (user_balance_delta[v.coupon.user_id] + v.win_amount).quantize(Q2)

            coeff_f = float(coeff)
            win_f = float(v.win_amount)

            if (coeff_f > best_multiplier["x"]) or (coeff_f == best_multiplier["x"] and win_f > best_multiplier["sum"]):
                best_multiplier = {"x": coeff_f, "sum": win_f}

            if v.win_amount > round_max_variant_win:
                round_max_variant_win = v.win_amount
                biggest_win = {"sum": float(v.win_amount), "x": coeff_f}
            elif v.win_amount == round_max_variant_win and coeff_f > biggest_win["x"]:
                biggest_win = {"sum": float(v.win_amount), "x": coeff_f}
        else:
            v.win_multiplier = Decimal("0.00")
            v.win_amount = Decimal("0.00")
            v.is_win = False

    BetVariant.objects.bulk_update(variants, ["win_amount", "win_multiplier", "is_win"])

    # обновляем купоны
    coupons = list(
        BetCoupon.objects.filter(round=round_obj).select_related("user").only("id", "user_id")
    )
    if coupons:
        for c in coupons:
            total = coupon_total_win.get(c.id, Decimal("0.00")).quantize(Q2)
            c.win_amount_total = total
            c.is_winner = total > 0
            c.is_seen = True

        # лучший купон на юзера → непросмотренный
        best_by_user: dict[int, BetCoupon] = {}
        for c in coupons:
            if not c.is_winner:
                continue
            prev = best_by_user.get(c.user_id)
            if prev is None or c.win_amount_total > prev.win_amount_total:
                best_by_user[c.user_id] = c
        for c in best_by_user.values():
            c.is_seen = False

        BetCoupon.objects.bulk_update(coupons, ["win_amount_total", "is_winner", "is_seen"])

    # глобальный рекорд (BiggestWin)
    if round_max_variant_win > Decimal("0.00"):
        obj, created = BiggestWin.objects.get_or_create(id=1, defaults={"amount": round_max_variant_win})
        if not created:
            if (
                round_max_variant_win > obj.amount
                or timezone.now() >= obj.updated_at + timedelta(days=7)
            ):
                obj.amount = round_max_variant_win
                obj.save(update_fields=["amount"])

    # обновляем балансы пользователей
    if user_balance_delta:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = list(User.objects.filter(id__in=user_balance_delta.keys()).only("id", "balance_cached"))
        for u in users:
            u.balance_cached = (u.balance_cached + user_balance_delta[u.id]).quantize(Q2)
        User.objects.bulk_update(users, ["balance_cached"])

    # финализация
    _finalize_round_with_stats(
        round_obj=round_obj,
        total_win=total_win,
        count_winners_by_category=count_winners_by_category,
        payout_by_category_dec=payout_by_category_dec,
        best_multiplier=best_multiplier,
        biggest_win=biggest_win,
    )


def _finalize_round_with_stats(
    *,
    round_obj: Round,
    total_win: Decimal,
    count_winners_by_category: dict[str, int],
    payout_by_category_dec: dict[str, Decimal],
    best_multiplier: dict,
    biggest_win: dict,
) -> None:
    """Завершает раунд и создаёт RoundStats с актуальными полями."""
    round_obj.status = Round.Status.FINISHED
    round_obj.end_time = timezone.now()
    round_obj.save(update_fields=["status", "end_time"])

    payout_by_category = {k: float(v) for k, v in payout_by_category_dec.items()}

    RoundStats.objects.create(
        round=round_obj,
        total_win=total_win,
        count_winners_by_category=count_winners_by_category,
        payout_by_category=payout_by_category,
        best_multiplier=best_multiplier,
        biggest_win=biggest_win,
    )
