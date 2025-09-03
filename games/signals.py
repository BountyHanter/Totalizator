from decimal import Decimal

from django.db.models.signals import post_migrate, post_delete, post_save
from django.dispatch import receiver

from games.models.bets import SelectedOutcome, BetCoupon
from games.models.jackpot import Jackpot
from games.models.payout import PayoutCategory


@receiver(post_migrate)
def create_payout_categories(sender, app_config, **kwargs):
    if app_config.label != "games":
        return
    for i in range(1, 11):
        PayoutCategory.objects.get_or_create(
            matched_count=i,
            defaults={
                'percent': 0,
                'active': i >= 6
            }
        )

    # создать джекпот, если его ещё нет
    Jackpot.objects.get_or_create(id=1, defaults={'amount': 0})

@receiver(post_save, sender=BetCoupon)
def update_live_pool_on_create(sender, instance, created, **kwargs):
    if created:
        instance.round.live_pool = (instance.round.live_pool + instance.amount_total).quantize(Decimal("0.01"))
        instance.round.save(update_fields=["live_pool"])