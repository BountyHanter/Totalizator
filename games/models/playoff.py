from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from games.models.rounds import Round
from teams.models.teams import Team

User = get_user_model()


class Playoff(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    start_round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="+")
    end_round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    started = models.BooleanField(default=False)
    finished = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    winner = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)

class PlayoffMatch(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        VOTING = "VOTING"
        FINISHED = "FINISHED"

    playoff = models.ForeignKey(Playoff, on_delete=models.CASCADE, related_name="matches")
    # ключевое поле:
    stage_slots = models.PositiveIntegerField(help_text="Номинальная стадия: 16, 8, 4, 2")
    pair_index = models.PositiveIntegerField(help_text="Порядковый номер пары в стадии, начиная с 1")

    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="playoff_team1")
    team2 = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="playoff_team2")
    seed1 = models.PositiveIntegerField(help_text="Посев team1 в момент старта стадии")
    seed2 = models.PositiveIntegerField(null=True, blank=True, help_text="Посев team2 в момент старта стадии")

    is_bye = models.BooleanField(default=False, help_text="Автопроход (нет соперника)")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    winner = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="playoff_winner")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @property
    def stage_label(self) -> str:
        """Красивое название стадии плей-офф"""
        mapping = {
            16: "1/16",
            8: "1/8",
            4: "1/4",
            2: "1/2",
            1: "Финал",
        }
        return mapping.get(self.stage_slots, f"1/{self.stage_slots}")



class FanVote(models.Model):
    class Strategy(models.TextChoices):
        ATTACK = "attack", "Атака"
        DEFENSE = "defense", "Защита"
        SPEED = "speed", "Скорость"
        TACTIC = "tactic", "Тактика"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    match = models.ForeignKey(PlayoffMatch, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    strategy = models.CharField(max_length=20, choices=Strategy.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "match")
        verbose_name = "Голос фаната"
        verbose_name_plural = "Голоса фанатов"

    def __str__(self):
        return f"{self.user} → {self.team.name} ({self.strategy})"
