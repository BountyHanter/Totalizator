from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class PayoutCategory(models.Model):
    matched_count = models.PositiveSmallIntegerField(
        unique=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10)
        ]
    )
    coefficient = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["matched_count"],
                name="payout_active_matched_idx",
                condition=Q(active=True),
            ),
        ]
