from games.models.playoff import Playoff, PlayoffMatch
from games.models.rounds import Round
from teams.models.teams import Team

def next_pow2(n: int) -> int:
    if n <= 1:
        return 1
    p = 1
    while p < n:
        p <<= 1
    return p


def stage2_create_playoff(ctx, stdout):
    """Этап 2 — создание турнира и генерация первого раунда"""
    pool = ctx["pool"]
    teams = ctx["teams"]

    stdout.write("▶ Этап 2: создание плей-офф и генерация пар")

    num_teams = len(teams)
    if num_teams == 1:
        # авто-победитель
        winner_id = teams[0]["id"]
        playoff = Playoff.objects.create(
            total_amount=pool.amount,
            winner_id=winner_id,
            started=True,
            finished=True,
        )
        Team.objects.filter(id=winner_id).update(fanpoints=0)
        pool.checkpoint_amount = pool.amount
        pool.amount = 0
        pool.save(update_fields=["amount", 'checkpoint_amount'])
        stdout.write(f"🏆 Турнир завершён сразу: победитель — {teams[0]['name']}")
        return {"playoff": playoff, "matches": []}

    stage_slots = next_pow2(num_teams)

    start_round = Round.objects.get(id=ctx["current_round_id"])
    playoff = Playoff.objects.create(
        total_amount=pool.amount,
        started=True,
        start_round=start_round,  # ✅ теперь поле заполняется
    )

    pairs = []
    for i in range(0, num_teams, 2):
        team1 = teams[i]
        team2 = teams[i + 1] if i + 1 < num_teams else None
        is_bye = team2 is None
        match = PlayoffMatch.objects.create(
            playoff=playoff,
            stage_slots=stage_slots,
            pair_index=i // 2 + 1,
            team1_id=team1["id"],
            team2_id=team2["id"] if team2 else None,
            seed1=i + 1,
            seed2=i + 2 if team2 else None,
            is_bye=is_bye,
            winner_id=team1["id"] if is_bye else None,
        )
        pairs.append(match)
        label = f"{team1['name']} vs {team2['name']}" if team2 else f"{team1['name']} (автопроход)"
        stdout.write(f"Создан матч: {label}")

    # ✅ Новое: первая стадия сразу в голосование
    PlayoffMatch.objects.filter(playoff=playoff, stage_slots=stage_slots).update(status="VOTING")
    stdout.write("🗳️ Первая стадия переведена в статус голосования (VOTING)\n")

    # Сброс FanPoints и фонда
    Team.objects.update(fanpoints=0)
    pool.amount = 0
    pool.save(update_fields=["amount"])

    stdout.write(f"✅ Сгенерировано матчей: {len(pairs)}")
    stdout.write(f"\n💰 Фонд обнулён, фанпоинты сброшены\n")

    return {"playoff": playoff, "matches": pairs}
