from django.contrib import admin
from django.db.models import Prefetch

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
# from games.models.jackpot import Jackpot
from games.models.matchs import Match
from games.models.payout import PayoutCategory
from games.models.rounds import Round, RoundStats
from games.models.wins import BiggestWin


@admin.register(PayoutCategory)
class PayoutCategoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Round)
admin.site.register(RoundStats)
admin.site.register(Match)

# @admin.register(Jackpot)
# class JackpotAdmin(admin.ModelAdmin):
#     def has_add_permission(self, request):
#         # Запрещает добавление новых записей
#         return False
#
#     def has_delete_permission(self, request, obj=None):
#         # Запрещает удаление записей
#         return False

class SelectedOutcomeInline(admin.TabularInline):
    model = SelectedOutcome
    extra = 0
    readonly_fields = ["match", "outcome", "result_icon"]
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(BetVariant)
class BetVariantAdmin(admin.ModelAdmin):
    inlines = [SelectedOutcomeInline]
    list_display = ["id", "coupon_id", "matched_count", "win_amount", "is_win"]
    list_select_related = ["coupon", "coupon__user", "coupon__round"]
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch(
                "selected",
                queryset=SelectedOutcome.objects.select_related(
                    "match__team1",
                    "match__team2",
                    "match__round"
                )
            )
        )

class BetCouponAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "round", "amount_total", "num_variants", "created_at"]
    readonly_fields = ["created_at"]

admin.site.register(BetCoupon, BetCouponAdmin)

@admin.register(BiggestWin)
class BiggestWinAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Запретить создание новой записи, если одна уже есть
        return not BiggestWin.objects.exists()

    def changelist_view(self, request, extra_context=None):
        # Вместо списка — сразу форма редактирования единственной записи
        obj = BiggestWin.objects.first()
        if obj:
            return self.change_view(request, str(obj.pk))
        return super().changelist_view(request, extra_context=extra_context)