from django.db import models
from solo.models import SingletonModel



class FanPool(SingletonModel):
    percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        help_text="Процент от всех ставок в раунде, идущий в фонд"
    )
    rounds_interval = models.PositiveIntegerField(default=1000, help_text="Каждые N раундов разыгрывать фонд")
    amount = models.DecimalField(max_digits=12, decimal_places=4, default=0.00, help_text="Текущая сумма фонда")
    checkpoint_amount = models.DecimalField(max_digits=12, decimal_places=4, default=0.00, help_text="Зафиксированная сумма фонда")

    def __str__(self):
        return f"FanPool: {self.amount} (каждые {self.rounds_interval} раундов)"