from django.db import models

from games.models.rounds import Round
from teams.models.teams import Team


class Match(models.Model):
    class Outcome(models.TextChoices):
        WIN_1 = '1', 'Победа 1'
        DRAW = 'X', 'Ничья'
        WIN_2 = '2', 'Победа 2'

    round = models.ForeignKey(Round, related_name='matches', on_delete=models.CASCADE)
    team1 = models.ForeignKey(Team, related_name='+', on_delete=models.CASCADE)
    team2 = models.ForeignKey(Team, related_name='+', on_delete=models.CASCADE)
    result = models.CharField(
        max_length=1,
        choices=Outcome.choices,
        blank=True,
        null=True,
        help_text="Итоговый результат: '1', 'X' или '2'"
    )

    def __str__(self):
        return f"{self.team1} vs {self.team2} (Раунд {self.round.id})"