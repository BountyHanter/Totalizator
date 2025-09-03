from django.db import models


class Round(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидание начала"
        SELECTION = 'selection', 'Выбор ставок'
        CALCULATION = 'calculation', 'Расчёт результатов'
        PAYOUT = 'payout', 'Выплата'
        FINISHED = 'finished', 'Завершён'

    start_time = models.DateTimeField(null=True, blank=True)
    selection_end_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    live_pool = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Текущий пул ставок (живой, обновляется при создании купонов)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SELECTION
    )
    game_hash = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f"Раунд {self.id}"

    class Meta:
        indexes = [
            # Уже покрывает CurrentRoundView / CurrentRoundPoolView / RoundHistoryView
            models.Index(fields=["status", "-id"], name="round_status_id_desc"),
        ]


class RoundStats(models.Model):
    round = models.OneToOneField(Round, on_delete=models.CASCADE, related_name="stats")

    created_at = models.DateTimeField(auto_now_add=True)

    total_pool = models.DecimalField(max_digits=12, decimal_places=2)
    payout_pool = models.DecimalField(max_digits=12, decimal_places=2)
    jackpot_before = models.DecimalField(max_digits=12, decimal_places=2)
    jackpot_after = models.DecimalField(max_digits=12, decimal_places=2)
    total_win = models.DecimalField(max_digits=12, decimal_places=2)

    count_winners_by_category = models.JSONField(default=dict)
    payout_by_category = models.JSONField(default=dict)
    best_multiplier = models.JSONField(default=dict)
    biggest_win = models.JSONField(default=dict)


    def __str__(self):
        return f"Статистика раунда {self.round.id}"
