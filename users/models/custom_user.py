from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Кастомный пользователь — пока без новых полей,
    но готов к расширению в будущем.
    """
    balance_cached = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
        verbose_name="Кэш баланса"
    )
