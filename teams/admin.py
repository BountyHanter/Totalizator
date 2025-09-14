from django.contrib import admin
from django.utils.html import format_html
from teams.models.teams import Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "is_active", "avatar_preview")
    readonly_fields = ("avatar_preview",)

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="height: 40px;"/>', obj.avatar_url)
        return "—"
    avatar_preview.short_description = "Аватар"
