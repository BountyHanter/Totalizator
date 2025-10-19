from decimal import Decimal
from django.db.models import F
from games.models.fanfool import FanPool
from games.models.rounds import Round
from games.models.playoff import Playoff
from teams.models.teams import Team


def stage1_prepare(stdout):
    """Этап 1 — Проверки и подготовка к старту турнира"""
    stdout.write("▶ Этап 1: проверка условий запуска плей-офф")

    pool = FanPool.get_solo()
    if not pool:
        stdout.write("❌ FanPool не найден")
        return None

    if pool.amount <= Decimal("0.00"):
        stdout.write("⚠️ Фонд пуст, розыгрыш невозможен")
        return None

    # === Загружаем команды (с fanpoints > 0) ===
    teams = list(
        Team.objects.filter(fanpoints__gt=0)
        .order_by("-fanpoints")
        .values("id", "name", "fanpoints")
    )
    if not teams:
        stdout.write("⚠️ Нет команд с FanPoints, запуск пропущен")
        return None

    # --- 🔥 БОНУС 1.1x для топ-3 команд ---
    top3_ids = [t["id"] for t in teams[:3]]
    Team.objects.filter(id__in=top3_ids).update(fanpoints=F("fanpoints") * Decimal("1.10"))

    # перезагружаем, чтобы вывести актуальные данные
    updated_top3 = Team.objects.filter(id__in=top3_ids).values("name", "fanpoints")
    for t in updated_top3:
        stdout.write(f"🏅 Бонус 1.1x → {t['name']}: {round(t['fanpoints'], 2)} FP")

    stdout.write("✅ Бонус применён к топ-3 командам.\n")

    # === Проверка активного раунда ===
    current_round_id = (
        Round.objects
        .filter(status=Round.Status.SELECTION)
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )
    if not current_round_id:
        stdout.write("❌ Нет активного раунда со статусом SELECTION")
        return None

    if current_round_id % pool.rounds_interval != 0:
        stdout.write(f"⏳ Раунд #{current_round_id} не кратен {pool.rounds_interval}")
        return None

    if Playoff.objects.filter(finished=False).exists():
        stdout.write("❌ Уже есть активный незавершённый плей-офф")
        return None

    # === Выводим список команд ===
    stdout.write("✅ Команды, участвующие в плей-офф:")
    for idx, t in enumerate(teams, start=1):
        stdout.write(f"{idx}. {t['name']} — {t['fanpoints']} FP")

    stdout.write(f"\nВсе проверки пройдены ✅\nФонд: {pool.amount}\nКоманд: {len(teams)}\n")

    return {
        "pool": pool,
        "teams": teams,
        "current_round_id": current_round_id,
    }
