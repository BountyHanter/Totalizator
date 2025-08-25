from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PayoutCategory(models.Model):
    matched_count = models.PositiveSmallIntegerField(
        unique=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10)
        ]
    )
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    active = models.BooleanField(default=True)

    def clean(self):
        total = sum(
            PayoutCategory.objects.filter(active=True).exclude(pk=self.pk).values_list('percent', flat=True)
        ) + self.percent
        if total > 100:
            raise ValidationError("Суммарный процент не может превышать 100%")