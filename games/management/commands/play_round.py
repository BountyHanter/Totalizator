import time
from decimal import Decimal

from django.core.management import BaseCommand
from django.utils import timezone

from games.management.commands.logger import log
from games.models.bets import BetVariant
from games.models.jackpot import Jackpot
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats

SELECTION_DURATION = 5
CALCULATION_DURATION = 15
PAYOUT_DURATION = 15

class Command(BaseCommand):
    help = "Проигрывание раунда"

    def handle(self, *args, **options):
        jackpot: Jackpot = get_jackpot()
        jackpot_before = jackpot.amount

        round = get_round()
        if not round:
            log.warning("Нет доступного раунда для проигрывания")
            time.sleep(60)
            return
        log.info(f"Начинается раунд {round}",
                 extra={"jackpot_before": jackpot_before,
                        "total_pool": round.total_pool})
        log.info(f"Доступный джекпот - {jackpot_before}")

        round.status = Round.Status.SELECTION
        round.start_time = timezone.now()
        # Чтобы избежать лишней нагрузки и обновить только те поля которые мы трогали
        round.save(update_fields=["start_time", "status"])
        log.info("Переводим в статус ставок")


        time.sleep(SELECTION_DURATION)

        round.status = Round.Status.CALCULATION
        round.save(update_fields=["status"])
        log.info("Переводим в статус подсчёта")

        calculation_start = time.monotonic()

        round.refresh_from_db()
        payout_pool_raw = round.total_pool * Decimal("0.95")

        log.info(f"Общий пул {payout_pool_raw}")

        categories = PayoutCategory.objects.filter(active=True).order_by('matched_count')
        if not categories:
            log.error("Нет категорий для выигрыша")
            return

        min_category = categories[0].matched_count

        win_payout = {}
        for i in categories:
            win_payout[i.matched_count] = payout_pool_raw * (i.percent / Decimal("100"))

        log.info(f"Выплаты - {win_payout}")

        calculation_elapsed = time.monotonic() - calculation_start
        calculation_sleep = max(0, CALCULATION_DURATION - calculation_elapsed)
        time.sleep(calculation_sleep)

        round.status = Round.Status.PAYOUT
        round.save(update_fields=["status"])
        log.info("Переводим в статус выплат")

        payout_start = time.monotonic()

        winners_by_category = {}

        for key in win_payout:
            variants = BetVariant.objects.filter(
                coupon__round=round,
                matched_count__gte=key
            ).exclude(
                matched_count__lt=min_category
            )
            if not variants.exists():
                jackpot.amount += win_payout[key]
                log.info(f"Нет угаданных {key} вариантов, добавляем к джекпоту {win_payout[key]}")
                jackpot.save(update_fields=["amount"])
                log.info(f"Новая сумма джекпота {jackpot.amount}")
                continue

            # Сначала собираем ставки на каждый вариант
            variant_bets = []
            total_variant_bets = Decimal("0")

            for variant in variants.select_related("coupon"):
                bet = variant.coupon.amount_total / variant.coupon.num_variants
                variant_bets.append((variant, bet))
                total_variant_bets += bet

            log.info(
                f"Обнаружено {variants.count()} вариантов, подходящих под категорию {key}. Общая сумма ставок: {total_variant_bets}")

            winners_by_category[key] = {
                "count": variants.count(),
                "sum": str(total_variant_bets)  # строкой — JSONField не сериализует Decimal
            }

            # если 10 — прибавим джекпот
            category_prize = win_payout[key]
            if key == 10:
                category_prize += jackpot.amount
                log.info(f"Приз для угаданных вариантов - 10 с джекпотом - {category_prize}")
                jackpot.amount = Decimal("0")
                jackpot.save(update_fields=["amount"])

            # Выплаты
            for variant, bet in variant_bets:
                user = variant.coupon.user
                if total_variant_bets > 0:
                    share = bet / total_variant_bets
                    payout = category_prize * share
                    variant.win_amount += payout
                    variant.is_win = True
                    variant.save(update_fields=["win_amount", "is_win"])
                    user.balance_cached += payout
                    user.save(update_fields=["balance_cached"])
                    log.info(
                        f"Выплата пользователю {user.id} ({user.username}) — {payout:.2f} USD "
                        f"по категории {key} (вариант #{variant.id})"
                    )

        payout_elapsed = time.monotonic() - payout_start
        payout_sleep = max(0, PAYOUT_DURATION - payout_elapsed)
        time.sleep(payout_sleep)

        round.status = Round.Status.FINISHED
        round.end_time = timezone.now()
        round.save(update_fields=["status", "end_time"])
        log.info("Переводим в статус завершения")

        RoundStats.objects.create(
            round=round,
            total_pool=round.total_pool,
            payout_pool=payout_pool_raw,
            jackpot_before=jackpot_before,
            jackpot_after=jackpot.amount,
            winners_by_category=winners_by_category,
        )


def get_round():
    round = Round.objects.filter(status=Round.Status.WAITING).order_by('id').first()
    return round

def get_jackpot():
    return Jackpot.objects.get(id=1)
