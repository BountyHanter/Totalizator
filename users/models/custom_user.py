from django.contrib.auth.models import AbstractUser
from django.db import models

from teams.models.teams import Team


class CustomUser(AbstractUser):
    """
    Кастомный пользователь — пока без новых полей,
    но готов к расширению в будущем.
    """
    balance_cached = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=50_000,
        verbose_name="Кэш баланса"
    )
    favorite_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fans",
        verbose_name="Любимая команда"
    )