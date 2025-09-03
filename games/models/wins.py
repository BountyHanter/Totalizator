from django.db import models
from django.core.exceptions import ValidationError

class BiggestWin(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk and BiggestWin.objects.exists():
            raise ValidationError("Можно создать только одну запись BiggestWin")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Удаление запрещено. Разрешено только обновление записи.")

    def __str__(self):
        return f"Самый большой выигрыш за неделю: {self.amount}"
