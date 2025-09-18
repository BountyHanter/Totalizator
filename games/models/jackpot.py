# from django.db import models
#
#
# class Jackpot(models.Model):
#     amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return f"Джекпот: {self.amount} USD"
#
#     class Meta:
#         verbose_name = "Джекпот"
#         verbose_name_plural = "Джекпот"
#
#     def save(self, *args, **kwargs):
#         if not self.pk and Jackpot.objects.exists():
#             raise ValueError("Можно создать только один экземпляр Jackpot")
#         return super().save(*args, **kwargs)
