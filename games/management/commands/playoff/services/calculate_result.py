import random
from collections import Counter
from games.models.playoff import FanVote

# Возможные множители — усиливают или ослабляют стратегии случайным образом
MULTIPLIERS = [1.05, 1.10, 1.13, 1.16]

# Схема "камень-ножницы-бумага"
WIN_MAP = {
    "attack": "defense",  # Атака бьёт Защиту
    "defense": "speed",   # Защита бьёт Скорость
    "speed": "tactic",    # Скорость бьёт Тактику
    "tactic": "attack",   # Тактика бьёт Атаку
}


def calculate_match_result(match, stdout=None):
    """
    Рассчитывает победителя матча плей-офф по голосам фанатов.
    Учитывает случайные множители и схему 'камень-ножницы-бумага'.
    """
    def log(msg):
        if stdout:
            stdout.write(str(msg))

    votes = FanVote.objects.filter(match=match)

    log(f"\n⚔️  Матч: {match.team1.name} vs {match.team2.name}")

    # Если нет голосов — авто-победа по seed
    if not votes.exists():
        winner = match.team1 if match.seed1 < (match.seed2 or 999) else match.team2
        log("⚠️  Нет голосов — победа по seed.")
        log(f"🏆 Победитель: {winner.name}\n")
        return winner

    # Вспомогательная функция — распределение голосов в процентах
    def get_distribution(team):
        team_votes = votes.filter(team=team)
        c = Counter(team_votes.values_list("strategy", flat=True))
        total = sum(c.values()) or 1
        return {
            "attack": c.get("attack", 0) * 100 / total,
            "defense": c.get("defense", 0) * 100 / total,
            "speed":  c.get("speed", 0) * 100 / total,
            "tactic": c.get("tactic", 0) * 100 / total,
        }

    # 1️⃣ Считаем проценты
    s1 = get_distribution(match.team1)
    s2 = get_distribution(match.team2)
    log(f"📊 Распределение голосов:")
    log(f"   {match.team1.name}: {s1}")
    log(f"   {match.team2.name}: {s2}")

    # 2️⃣ Применяем случайные множители
    multipliers1 = random.sample(MULTIPLIERS, len(MULTIPLIERS))
    multipliers2 = random.sample(MULTIPLIERS, len(MULTIPLIERS))
    keys = list(s1.keys())

    for strat, m1, m2 in zip(keys, multipliers1, multipliers2):
        s1[strat] *= m1
        s2[strat] *= m2

    log(f"🎲 Применены множители:")
    log(f"   {match.team1.name}: {dict(zip(keys, multipliers1))}")
    log(f"   {match.team2.name}: {dict(zip(keys, multipliers2))}")

    log(f"📈 После множителей:")
    log(f"   {match.team1.name}: {s1}")
    log(f"   {match.team2.name}: {s2}")

    # 3️⃣ Сравнение по WIN_MAP
    score1 = score2 = 0
    log("⚔️  Сравнение стратегий:")
    for strat, beats in WIN_MAP.items():
        a_val = s1[strat]
        b_val = s2[beats]
        diff = round(abs(a_val - b_val), 2)

        if a_val > b_val:
            score1 += (a_val - b_val)
            log(f"   {match.team1.name}: {strat} ({a_val:.2f}) > {beats} ({b_val:.2f}) → +{diff}")
        elif b_val > a_val:
            score2 += (b_val - a_val)
            log(f"   {match.team2.name}: {beats} ({b_val:.2f}) > {strat} ({a_val:.2f}) → +{diff}")
        else:
            log(f"   {strat} vs {beats}: ничья")

    log(f"📊 Очки: {match.team1.name} = {score1:.2f}, {match.team2.name} = {score2:.2f}")

    # 4️⃣ Определяем победителя
    if abs(score1 - score2) < 0.0001:
        winner = match.team1 if match.seed1 < (match.seed2 or 999) else match.team2
        log("🤝 Ничья → победа по seed.")
    else:
        winner = match.team1 if score1 > score2 else match.team2

    log(f"🏆 Победитель: {winner.name}\n")
    return winner
