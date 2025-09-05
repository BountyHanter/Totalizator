from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import CustomUser, ColorInterval


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('balance_cached',)}),
    )
    readonly_fields = ('balance_cached',)


@admin.register(ColorInterval)
class ColorIntervalAdmin(admin.ModelAdmin):
    list_display = ("start_value", "end_value", "background_color", "border_color")
    list_filter = ("background_color", "border_color")
    search_fields = ("start_value", "end_value", "background_color", "border_color")