from django.db import models

from games.models.payout import PayoutScheme


class ColorInterval(models.Model):
    payout_scheme = models.ForeignKey(
        PayoutScheme,
        on_delete=models.CASCADE,
        related_name="color_intervals",
        verbose_name="Схема выплат"
    )

    start_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Начало интервала")
    end_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Конец интервала")

    background_color = models.CharField(max_length=7, help_text="HEX цвет для фона (например, #353353)")
    border_color = models.CharField(max_length=7, help_text="HEX цвет для рамки (например, #454242)")

    def as_dict(self):
        return {
            "background": self.background_color,
            "border": self.border_color
        }

    def __str__(self):
        return f"{self.payout_scheme.name}: {self.start_value} – {self.end_value}"
