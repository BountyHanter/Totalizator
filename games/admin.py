from django.contrib import admin

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.jackpot import Jackpot
from games.models.matchs import Match
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats


@admin.register(PayoutCategory)
class PayoutCategoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Round)
admin.site.register(RoundStats)
admin.site.register(Match)

@admin.register(Jackpot)
class JackpotAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Запрещает добавление новых записей
        return False

    def has_delete_permission(self, request, obj=None):
        # Запрещает удаление записей
        return False

class SelectedOutcomeInline(admin.TabularInline):
    model = SelectedOutcome
    extra = 0

class BetVariantAdmin(admin.ModelAdmin):
    inlines = [SelectedOutcomeInline]

class BetCouponAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "round", "amount_total", "num_variants", "created_at"]
    readonly_fields = ["created_at"]

admin.site.register(BetCoupon, BetCouponAdmin)
admin.site.register(BetVariant, BetVariantAdmin)