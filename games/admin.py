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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            'selected',  # related_name в SelectedOutcome
            'selected__match'  # чтобы матч не тянулся по отдельному запросу
        )

class BetCouponAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "round", "amount_total", "num_variants", "created_at"]
    readonly_fields = ["created_at"]

admin.site.register(BetCoupon, BetCouponAdmin)
admin.site.register(BetVariant, BetVariantAdmin)