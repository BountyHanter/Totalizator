from django.db.models import Q, Count, Subquery, OuterRef, IntegerField
from django.db.models.functions import Coalesce

from games.models.bets import BetVariant, SelectedOutcome
from games.models.matchs import Match


def recompute_matched_counts(round_obj):
    """
    Пересчитывает matched_count для всех BetVariant указанного раунда.
    Использует подзапрос — выполняется одним SQL-запросом без загрузки данных в память.
    """

    # Подзапрос: считаем количество угаданных исходов для каждого варианта
    match_count_subquery = (
        SelectedOutcome.objects
        .filter(variant=OuterRef("pk"))
        .filter(
            (Q(outcome=SelectedOutcome.Outcome.WIN1, match__result=Match.Outcome.WIN_1)) |
            (Q(outcome=SelectedOutcome.Outcome.DRAW, match__result=Match.Outcome.DRAW)) |
            (Q(outcome=SelectedOutcome.Outcome.WIN2, match__result=Match.Outcome.WIN_2))
        )
        .values("variant")
        .annotate(cnt=Count("id"))
        .values("cnt")[:1]
    )

    # Обновляем matched_count подзапросом
    BetVariant.objects.filter(coupon__round=round_obj).update(
        matched_count=Coalesce(Subquery(match_count_subquery, output_field=IntegerField()), 0)
    )