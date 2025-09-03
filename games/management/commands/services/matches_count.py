from django.db.models import Q, Count
from games.models.bets import BetVariant, SelectedOutcome
from games.models.matchs import Match

def recompute_matched_counts(round_obj):
    # Все варианты в раунде
    variant_ids = list(
        BetVariant.objects.filter(coupon__round=round_obj).values_list("id", flat=True)
    )
    if not variant_ids:
        return

    # Обнулим matched_count одним апдейтом (для тех, у кого не будет совпадений)
    BetVariant.objects.filter(id__in=variant_ids).update(matched_count=0)

    # Посчитаем количество угаданных исходов на вариант:
    # selected outcome совпадает с фактическим результатом матча
    matched_rows = (
        SelectedOutcome.objects
        .filter(variant_id__in=variant_ids)
        .filter(
            (Q(outcome=SelectedOutcome.Outcome.WIN1) & Q(match__result=Match.Outcome.WIN_1)) |
            (Q(outcome=SelectedOutcome.Outcome.DRAW) & Q(match__result=Match.Outcome.DRAW)) |
            (Q(outcome=SelectedOutcome.Outcome.WIN2) & Q(match__result=Match.Outcome.WIN_2))
        )
        .values("variant_id")
        .annotate(cnt=Count("id"))
    )

    # Массовое обновление matched_count только там, где cnt > 0
    variants_map = {v.id: v for v in BetVariant.objects.filter(id__in=variant_ids).only("id", "matched_count")}
    to_update = []
    for row in matched_rows:
        v = variants_map.get(row["variant_id"])
        if v:
            v.matched_count = row["cnt"]
            to_update.append(v)

    if to_update:
        BetVariant.objects.bulk_update(to_update, ["matched_count"])
