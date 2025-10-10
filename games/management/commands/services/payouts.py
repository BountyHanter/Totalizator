from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.db import connection

from games.models.rounds import Round, RoundStats
from games.models.wins import BiggestWin

def update_variants_with_wins(round_obj):
    """
    Массовый расчёт win_multiplier, win_amount и is_win для всех BetVariant раунда.
    Работает напрямую через SQL (psycopg2), без загрузки ORM-объектов в память.
    """

    # 1. Загружаем все payout-схемы, участвующие в раунде
    from games.models.payout import PayoutScheme

    schemes = (
        PayoutScheme.objects.filter(coupons__round=round_obj)
        .distinct()
        .only("id", "coefficients")
    )

    if not schemes.exists():
        return 0  # нечего считать

    with connection.cursor() as cursor:
        total_updated = 0

        for scheme in schemes:
            # 2. Собираем CASE WHEN для matched_count
            coeffs = scheme.coefficients or {}
            if not coeffs:
                continue

            case_sql_parts = []
            for k, v in coeffs.items():
                try:
                    count_int = int(k)
                    coeff_val = Decimal(str(v))
                except Exception:
                    continue
                case_sql_parts.append(f"WHEN {count_int} THEN {coeff_val}")

            if not case_sql_parts:
                continue

            case_expr = "CASE v.matched_count " + " ".join(case_sql_parts) + " ELSE 0 END"

            # 3. Формируем SQL
            sql = f"""
                UPDATE games_betvariant AS v
                SET
                    win_multiplier = {case_expr},
                    win_amount = ROUND((c.amount_total / NULLIF(c.num_variants, 0)) * ({case_expr}), 2),
                    is_win = CASE WHEN ({case_expr}) > 0 THEN TRUE ELSE FALSE END
                FROM games_betcoupon AS c
                WHERE v.coupon_id = c.id
                  AND c.payout_scheme_id = %s
                  AND c.round_id = %s;
            """

            cursor.execute(sql, [scheme.id, round_obj.id])
            total_updated += cursor.rowcount

    return total_updated

def update_coupons_with_totals(round_obj):
    """
    Обновляет купоны указанного раунда одним SQL:
      • win_amount_total = сумма win_amount всех вариантов купона
      • is_winner = TRUE, если сумма > 0
      • is_seen = TRUE
    """
    with connection.cursor() as cursor:
        sql = """
            UPDATE games_betcoupon
            SET
                win_amount_total = COALESCE(s.sum_win, 0),
                is_winner        = (COALESCE(s.sum_win, 0) > 0),
                is_seen          = TRUE
            FROM (
                SELECT
                    c.id AS cid,
                    ROUND(COALESCE(SUM(v.win_amount), 0), 2) AS sum_win
                FROM games_betcoupon AS c
                LEFT JOIN games_betvariant AS v
                       ON v.coupon_id = c.id
                WHERE c.round_id = %s
                GROUP BY c.id
            ) AS s
            WHERE games_betcoupon.id = s.cid
              AND games_betcoupon.round_id = %s;
        """
        cursor.execute(sql, [round_obj.id, round_obj.id])
        return cursor.rowcount




def update_user_balances(round_obj):
    """
    Массовое обновление балансов пользователей по итогам раунда.
    Работает одним SQL-запросом. Поддерживает кастомные модели User.
    """
    User = get_user_model()
    user_table = User._meta.db_table  # <-- получаем реальное имя таблицы

    with connection.cursor() as cursor:
        sql = f"""
            UPDATE {user_table}
            SET balance_cached = ROUND({user_table}.balance_cached + s.sum_win, 2)
            FROM (
                SELECT
                    c.user_id uid,
                    COALESCE(SUM(c.win_amount_total), 0) sum_win
                FROM games_betcoupon c
                WHERE c.round_id = %s
                  AND c.is_winner = TRUE
                GROUP BY c.user_id
            ) s
            WHERE {user_table}.id = s.uid;
        """
        cursor.execute(sql, [round_obj.id])
        return cursor.rowcount


def get_best_and_biggest(round_obj):
    """
    Возвращает:
      best_multiplier — {x: float, sum: float}
      biggest_win — {x: float, sum: float}
    """
    sql = """
        SELECT
            MAX(v.win_multiplier) AS best_mult,
            MAX(v.win_amount) AS biggest_sum
        FROM games_betvariant v
        JOIN games_betcoupon c ON v.coupon_id = c.id
        WHERE c.round_id = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [round_obj.id])
        best_mult, biggest_sum = cursor.fetchone() or (0, 0)

    # получаем коэффициент для варианта с самой большой суммой выигрыша
    sql2 = """
        SELECT v.win_multiplier
        FROM games_betvariant v
        JOIN games_betcoupon c ON v.coupon_id = c.id
        WHERE c.round_id = %s
        ORDER BY v.win_amount DESC, v.win_multiplier DESC
        LIMIT 1;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql2, [round_obj.id])
        row = cursor.fetchone()
        biggest_x = float(row[0]) if row else 0.0

    return (
        {"x": float(best_mult or 0), "sum": float(biggest_sum or 0)},
        {"x": biggest_x, "sum": float(biggest_sum or 0)},
    )


def get_round_stats_by_matched(round_obj):
    """
    Возвращает:
      count_winners_by_category — словарь {matched_count: количество выигравших вариантов}
      payout_by_category — словарь {matched_count: общая сумма выигрышей}
    """
    count_winners_by_category = {str(i): 0 for i in range(1, 11)}
    payout_by_category = {str(i): 0.00 for i in range(1, 11)}

    sql = """
        SELECT v.matched_count, COUNT(*) AS cnt, SUM(v.win_amount) AS total
        FROM games_betvariant v
        JOIN games_betcoupon c ON v.coupon_id = c.id
        WHERE c.round_id = %s
        GROUP BY v.matched_count;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, [round_obj.id])
        for matched_count, cnt, total in cursor.fetchall():
            count_winners_by_category[str(matched_count)] = int(cnt or 0)
            payout_by_category[str(matched_count)] = float(total or 0)

    return count_winners_by_category, payout_by_category

def mark_best_coupons_unseen(round_obj):
    """
    Делает у каждого пользователя лучший выигравший купон (макс. win_amount_total)
    непросмотренным (is_seen=False).
    """
    with connection.cursor() as cursor:
        sql = """
            UPDATE games_betcoupon
            SET is_seen = FALSE
            FROM (
                SELECT user_id, MAX(win_amount_total) max_win
                FROM games_betcoupon
                WHERE round_id = %s AND is_winner = TRUE
                GROUP BY user_id
            ) subquery
            WHERE games_betcoupon.round_id = %s
              AND games_betcoupon.is_winner = TRUE
              AND games_betcoupon.user_id = subquery.user_id
              AND games_betcoupon.win_amount_total = subquery.max_win;
        """
        cursor.execute(sql, [round_obj.id, round_obj.id])
        return cursor.rowcount


@transaction.atomic
def process_payouts(round_obj: Round):
    """
    Полностью оптимизированный расчёт выплат по раунду.
    Все основные операции выполняются в SQL (UPDATE ... FROM ...),
    что исключает цикл по вариантам или купонам в Python.
    """
    # 1️⃣ Переводим раунд в статус PAYOUT
    round_obj.refresh_from_db()
    round_obj.status = Round.Status.PAYOUT
    round_obj.save(update_fields=["status"])

    start_ts = timezone.now()

    # 2️⃣ Массово пересчитываем все варианты (win_amount, win_multiplier, is_win)
    updated_variants = update_variants_with_wins(round_obj)

    # 3️⃣ Агрегируем результаты по купонам (win_amount_total, is_winner, is_seen)
    updated_coupons = update_coupons_with_totals(round_obj)

    mark_best_coupons_unseen(round_obj)

    # 4️⃣ Массово обновляем балансы пользователей
    updated_users = update_user_balances(round_obj)

    # 5️⃣ Считаем статистику (через ORM, нагрузка уже минимальна)
    from django.db.models import Sum, Max, Count

    stats = Round.objects.filter(id=round_obj.id).values("id").annotate(
        total_win=Sum("coupons__win_amount_total"),
        winners=Count("coupons", filter=Q(coupons__is_winner=True)),
    ).first() or {}

    total_win = stats.get("total_win") or Decimal("0.00")
    winners = stats.get("winners") or 0

    count_winners_by_category, payout_by_category = get_round_stats_by_matched(round_obj)
    best_multiplier, biggest_win = get_best_and_biggest(round_obj)

    # 6️⃣ Сохраняем RoundStats
    RoundStats.objects.create(
        round=round_obj,
        total_win=total_win,
        count_winners_by_category=count_winners_by_category,
        payout_by_category=payout_by_category,
        best_multiplier=best_multiplier,
        biggest_win=biggest_win,
    )

    # 7️⃣ Обновляем BiggestWin
    biggest = (
        round_obj.coupons.aggregate(m=Max("win_amount_total"))["m"]
        or Decimal("0.00")
    )
    if biggest > 0:
        obj, _ = BiggestWin.objects.get_or_create(id=1, defaults={"amount": biggest})
        if biggest > obj.amount or obj.updated_at <= timezone.now() - timedelta(days=7):
            obj.amount = biggest
            obj.save(update_fields=["amount"])

    # 8️⃣ Завершаем раунд
    round_obj.status = Round.Status.FINISHED
    round_obj.end_time = timezone.now()
    round_obj.save(update_fields=["status", "end_time"])