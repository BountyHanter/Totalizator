from django import forms
from django.contrib import admin
from django.db.models import Prefetch
from solo.admin import SingletonModelAdmin

from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.fanfool import FanPool
from games.models.matchs import Match
from games.models.payout import PayoutScheme
from games.models.rounds import Round, RoundStats
from games.models.wins import BiggestWin
from users.models import ColorInterval


class PayoutSchemeForm(forms.ModelForm):
    coeff_1 = forms.DecimalField(label="1 угаданный", max_digits=8, decimal_places=2)
    coeff_2 = forms.DecimalField(label="2 угаданных", max_digits=8, decimal_places=2)
    coeff_3 = forms.DecimalField(label="3 угаданных", max_digits=8, decimal_places=2)
    coeff_4 = forms.DecimalField(label="4 угаданных", max_digits=8, decimal_places=2)
    coeff_5 = forms.DecimalField(label="5 угаданных", max_digits=8, decimal_places=2)
    coeff_6 = forms.DecimalField(label="6 угаданных", max_digits=8, decimal_places=2)
    coeff_7 = forms.DecimalField(label="7 угаданных", max_digits=8, decimal_places=2)
    coeff_8 = forms.DecimalField(label="8 угаданных", max_digits=8, decimal_places=2)
    coeff_9 = forms.DecimalField(label="9 угаданных", max_digits=8, decimal_places=2)
    coeff_10 = forms.DecimalField(label="10 угаданных", max_digits=8, decimal_places=2)

    class Meta:
        model = PayoutScheme
        fields = ("name", "description", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coeffs = self.instance.coefficients or {}
        for i in range(1, 11):
            self.fields[f"coeff_{i}"].initial = coeffs.get(str(i), 0)

    def clean(self):
        cleaned = super().clean()
        coeffs = {}
        for i in range(1, 11):
            value = cleaned.get(f"coeff_{i}")
            if value is None:
                raise forms.ValidationError(f"Коэффициент для {i} угаданных обязателен")
            coeffs[str(i)] = value

        # здесь же проверяем количество ключей
        if set(coeffs.keys()) != {str(i) for i in range(1, 11)}:
            raise forms.ValidationError("Должно быть ровно 10 коэффициентов")

        cleaned["coefficients"] = coeffs
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.coefficients = {
            str(i): float(self.cleaned_data[f"coeff_{i}"]) for i in range(1, 11)
        }
        # full_clean тут можно вообще убрать, форма уже всё проверила
        if commit:
            instance.save()
        return instance


class ColorIntervalInline(admin.StackedInline):
    model = ColorInterval
    can_delete = False   # чтобы не удаляли связь случайно
    extra = 0


@admin.register(PayoutScheme)
class PayoutSchemeAdmin(admin.ModelAdmin):
    form = PayoutSchemeForm
    list_display = ("name", "active", "created_at", "updated_at")
    list_filter = ("active",)
    search_fields = ("name",)
    inlines = [ColorIntervalInline]

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

@admin.register(FanPool)
class FanPoolAdmin(SingletonModelAdmin):
    list_display = ("percent", "rounds_interval", "amount")