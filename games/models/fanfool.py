from django.db import models
from solo.models import SingletonModel



class FanPool(SingletonModel):
    percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        help_text="Процент от всех ставок в раунде, идущий в фонд"
    )
    rounds_interval = models.PositiveIntegerField(default=1000, help_text="Каждые N раундов разыгрывать фонд")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Текущая сумма фонда")

    rounds_since_distribution = models.PositiveIntegerField(default=0, verbose_name="Раундов прошло с розыгрыша")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FanPool: {self.amount} (каждые {self.rounds_interval} раундов)"