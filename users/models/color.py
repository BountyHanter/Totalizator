from django.db import models


class ColorInterval(models.Model):
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
        return f"{self.start_value} – {self.end_value}: bg={self.background_color}, border={self.border_color}"
