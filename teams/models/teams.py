import os

from django.conf import settings
from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    avatar = models.FilePathField(
        path=os.path.join(settings.MEDIA_ROOT, "team_avatars"),
        match=r".*\.(jpg|jpeg|png|gif|svg)$",   # допустимые расширения
        recursive=False,
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Аватар"
    )

    def __str__(self):
        return self.name

    @property
    def avatar_url(self):
        if self.avatar:
            # убираем MEDIA_ROOT, оставляем относительный путь
            rel_path = os.path.relpath(self.avatar, settings.MEDIA_ROOT)
            return f"{settings.MEDIA_URL}{rel_path}"
        return None