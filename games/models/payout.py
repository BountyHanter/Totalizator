from django.core.exceptions import ValidationError
from django.db import models


class PayoutScheme(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    coefficients = models.JSONField(
        default=dict,
        help_text="Словарь с коэффициентами для 1–10 угаданных матчей"
    )

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_coefficient(self, matched_count: int) -> float:
        """Вернёт коэффициент для указанного количества угаданных."""
        return float(self.coefficients.get(str(matched_count), 0.0))

    def __str__(self):
        return self.name
