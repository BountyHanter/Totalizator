from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.utils import timezone
from django.db.models import Sum

from games.models.bets import BetVariant
from games.models.jackpot import Jackpot
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats
from games.models.wins import BiggestWin

HOUSE_FEE = Decimal("0.05")  # комиссия 5%


def process_payouts(round_obj: Round):
    """
    Выплаты и финализация раунда.
    Обновляет варианты, балансы и пишет RoundStats.
    """
    jackpot = _get_or_create_jackpot()
    jackpot_before = jackpot.amount

    # ===== CALCULATION: считаем пул
    total_pool = round_obj.live_pool.quantize(Decimal("0.01"))

    payout_pool_raw = (total_pool * (Decimal("1.00") - HOUSE_FEE)).quantize(Decimal("0.01"))

    categories = list(PayoutCategory.objects.filter(active=True).order_by("matched_count"))
    if not categories:
        return

    min_cat = categories[0].matched_count
    max_cat = categories[-1].matched_count

    category_funds = {
        c.matched_count: (payout_pool_raw * (c.percent / Decimal("100"))).quantize(Decimal("0.01"))
        for c in categories
    }

    # ===== PAYOUT =====
    round_obj.status = Round.Status.PAYOUT
    round_obj.save(update_fields=["status"])

    count_winners_by_category = {str(c.matched_count): 0 for c in categories}
    payout_by_category_dec = {str(c.matched_count): Decimal("0.00") for c in categories}

    variant_acc = {}  # pk -> {"win_sum": Decimal, "bet": Decimal, "is_win": bool}
    user_balance_delta = defaultdict(Decimal)
    total_win = Decimal("0.00")

    for key in [c.matched_count for c in categories]:
        variants_qs = (
            BetVariant.objects
            .filter(coupon__round=round_obj, matched_count__gte=key)
            .exclude(matched_count__lt=min_cat)
            .select_related("coupon", "coupon__user")
        )

        winners_count = variants_qs.count()
        count_winners_by_category[str(key)] = winners_count

        if winners_count == 0:
            jackpot.amount = (jackpot.amount + category_funds[key]).quantize(Decimal("0.01"))
            jackpot.save(update_fields=["amount"])
            continue

        coupon_bet_cache: dict[int, Decimal] = {}
        variant_bets = []
        total_variant_bets = Decimal("0.00")

        for v in variants_qs:
            cid = v.coupon_id
            bet_amount = coupon_bet_cache.get(cid)
            if bet_amount is None:
                try:
                    bet_amount = (v.coupon.amount_total / v.coupon.num_variants).quantize(Decimal("0.01"))
                except Exception:
                    bet_amount = Decimal("0.00")
                coupon_bet_cache[cid] = bet_amount

            variant_bets.append((v, bet_amount))
            total_variant_bets += bet_amount

        category_prize = category_funds[key]
        if key == max_cat:
            category_prize = (category_prize + jackpot.amount).quantize(Decimal("0.01"))
            jackpot.amount = Decimal("0.00")
            jackpot.save(update_fields=["amount"])

        if total_variant_bets <= 0:
            continue

        for v, bet_amount in variant_bets:
            share = (bet_amount / total_variant_bets)
            payout = (category_prize * share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            acc = variant_acc.setdefault(
                v.pk, {"win_sum": Decimal("0.00"), "bet": bet_amount, "is_win": False}
            )
            acc["win_sum"] = (acc["win_sum"] + payout).quantize(Decimal("0.01"))
            acc["is_win"] = True

            user_balance_delta[v.coupon.user_id] += payout
            total_win += payout
            payout_by_category_dec[str(key)] = (payout_by_category_dec[str(key)] + payout).quantize(Decimal("0.01"))

    # ===== обновление вариантов
    if variant_acc:
        variant_ids = list(variant_acc.keys())
        variant_map = {
            v.pk: v for v in BetVariant.objects.filter(pk__in=variant_ids).select_related("coupon")
        }

        best_multiplier = {"x": 0.00, "sum": 0.00}
        biggest_win = {"sum": 0.00, "x": 0.00}

        for pk, acc in variant_acc.items():
            v = variant_map[pk]
            v.win_amount = (v.win_amount + acc["win_sum"]).quantize(Decimal("0.01"))
            v.is_win = acc["is_win"]

            bet_amount = acc["bet"]
            v.win_multiplier = (
                (v.win_amount / bet_amount).quantize(Decimal("0.01")) if bet_amount > 0 else Decimal("0.00")
            )

            win_amount_f = float(v.win_amount)
            win_mult_f = float(v.win_multiplier)

            if win_mult_f > best_multiplier["x"]:
                best_multiplier = {"x": win_mult_f, "sum": win_amount_f}
            if win_amount_f > biggest_win["sum"]:
                biggest_win = {"sum": win_amount_f, "x": win_mult_f}

        BetVariant.objects.bulk_update(variant_map.values(), ["win_amount", "win_multiplier", "is_win"])
    else:
        best_multiplier = {"x": 0.00, "sum": 0.00}
        biggest_win = {"sum": 0.00, "x": 0.00}

    # ===== обновление глобального рекорда BiggestWin (жизнь 7 дней)
    # Берём максимум из итоговых сумм выигрыша по вариантам (Decimal), а не из float в biggest_win
    max_variant_win = Decimal("0.00")
    for acc in variant_acc.values():
        if acc["win_sum"] > max_variant_win:
            max_variant_win = acc["win_sum"]
    max_variant_win = max_variant_win.quantize(Decimal("0.01"))

    if max_variant_win > Decimal("0.00"):
        obj, created = BiggestWin.objects.get_or_create(id=1, defaults={"amount": max_variant_win})
        if not created:
            # Переписываем, если новый больше или истёк срок в 7 дней
            if max_variant_win > obj.amount or timezone.now() >= obj.updated_at + timedelta(days=7):
                obj.amount = max_variant_win
                obj.save(update_fields=["amount"])

    # ===== обновление балансов пользователей
    if user_balance_delta:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = list(User.objects.filter(id__in=user_balance_delta.keys()).only("id", "balance_cached"))
        for u in users:
            u.balance_cached = (u.balance_cached + user_balance_delta[u.id]).quantize(Decimal("0.01"))
        User.objects.bulk_update(users, ["balance_cached"])

    # ===== FINISH =====
    round_obj.status = Round.Status.FINISHED
    round_obj.end_time = timezone.now()
    round_obj.save(update_fields=["status", "end_time"])

    payout_by_category = {k: float(v) for k, v in payout_by_category_dec.items()}

    RoundStats.objects.create(
        round=round_obj,
        total_pool=total_pool,
        payout_pool=payout_pool_raw,
        jackpot_before=jackpot_before,
        jackpot_after=jackpot.amount,
        total_win=total_win,
        count_winners_by_category=count_winners_by_category,
        payout_by_category=payout_by_category,
        best_multiplier=best_multiplier,
        biggest_win=biggest_win,
    )


def _get_or_create_jackpot():
    try:
        return Jackpot.objects.get(id=1)
    except Jackpot.DoesNotExist:
        return Jackpot.objects.create(id=1, amount=Decimal("0.00"))
