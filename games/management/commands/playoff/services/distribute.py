from decimal import Decimal, ROUND_DOWN
from collections import Counter
from django.db import transaction
from django.db.models import F, Sum, Q
from games.models.fanfool import FanPool
from games.models.playoff import FanVote
from games.models.bets import BetCoupon
from games.models.rounds import Round
from teams.models.teams import Team
from users.models import CustomUser


def _q2(x: Decimal) -> Decimal:
    return (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def distribute_fanpool(playoff, prev_playoff=None, stdout=None):
    """Распределение FanPool по победившим командам и их фанатам с подробными логами."""
    def log(msg=""):
        if stdout:
            stdout.write(str(msg))

    pool = FanPool.get_solo()
    if not pool or pool.checkpoint_amount <= 0:
        log("❗ FanPool пуст — распределять нечего.")
        return

    winners = list(getattr(playoff, "final_teams").values_list("id", flat=True)) if hasattr(playoff, "final_teams") else []
    total_teams = len(winners)
    if total_teams == 0:
        log("❗ Нет финалистов — фонд переносится (по правилам проекта).")
        return

    DISTRIBUTION_MAP = {
        4: [Decimal("44"), Decimal("26"), Decimal("15"), Decimal("15")],
        3: [Decimal("50"), Decimal("30"), Decimal("20")],
        2: [Decimal("66"), Decimal("34")],
        1: [Decimal("100")],
    }
    percents = DISTRIBUTION_MAP.get(total_teams, [Decimal("100")])

    total_amount = _q2(pool.checkpoint_amount)

    # === Заголовок розыгрыша
    log("════════════════════════════════════════════════════════════")
    log(f"🎁 РОЗЫГРЫШ FANPOOL")
    log(f"  • Сумма пула: {total_amount}")
    log(f"  • Команд-призёров: {total_teams}")
    log(f"  • Схема процентов: {', '.join([f'{p}%' for p in percents])}")
    log("════════════════════════════════════════════════════════════")

    with transaction.atomic():
        for idx, (team_id, percent) in enumerate(zip(winners, percents), start=1):
            team = Team.objects.get(id=team_id)
            team_reward = _q2(total_amount * percent / Decimal("100"))

            # --- Блок заголовка команды
            log("")
            log(f"🏆 Команда #{idx}: {team.name}")
            log(f"  • Приз команды: {team_reward} ({percent}%)")

            users_qs = CustomUser.objects.filter(favorite_team=team)
            users = list(users_qs)
            log(f"  • Фанатов (favorite_team): {len(users)}")

            if not users:
                log("  • Нет фанатов → приз не может быть распределён (по правилам: сгорает/переносится).")
                continue

            # Раунды, где команда участвовала, за интервал между плей-оффами
            team_round_ids_qs = Round.objects.filter(
                Q(matches__team1=team) | Q(matches__team2=team)
            ).values_list("id", flat=True)
            team_round_ids = list(team_round_ids_qs)

            if prev_playoff and getattr(prev_playoff, "end_round_id", None):
                lower_bound = prev_playoff.end_round_id
            else:
                lower_bound = 0

            upper_bound = getattr(playoff, "start_round_id", 10**12)  # защитный большой id, если нет поля

            round_ids_period = [rid for rid in team_round_ids if lower_bound < rid < upper_bound]
            log(f"  • Раунды с участием команды в периоде: {len(round_ids_period)}"
                + (f" (диапазон: {min(round_ids_period)}..{max(round_ids_period)})" if round_ids_period else ""))

            # Голоса в плей-офф (для этой команды)
            votes_qs = FanVote.objects.filter(match__playoff=playoff, team=team)
            team_total_votes = votes_qs.count()
            user_votes_cnt = Counter(votes_qs.values_list("user", flat=True))
            log(f"  • ΣVotes команды (в плей-офф): {team_total_votes}")

            # FanPoints команды и пользователей
            total_team_fanpoints = Decimal(team.fanpoints or 0)
            log(f"  • ΣFanPoints команды: {total_team_fanpoints}")

            # Ставки пользователей в нужных раундах команды и периоде
            user_bets_qs = (
                BetCoupon.objects.filter(
                    user__in=users,
                    round_id__in=round_ids_period
                )
                .values("user")
                .annotate(total_stake=Sum("amount_total"))
            )
            user_stakes = {row["user"]: Decimal(row["total_stake"] or 0) for row in user_bets_qs}
            total_stakes_team = sum(user_stakes.values(), Decimal("0"))
            log(f"  • ΣСтавок фанатов (в раундах команды за период): {total_stakes_team}")

            # Выбор весов (A,B): если голосов у команды нет вообще — весь вес на FanPoints
            if team_total_votes == 0:
                a_weight, b_weight = Decimal("1.0"), Decimal("0.0")
                log("  • Вес формулы: A=1.0 (FanPoints), B=0.0 (Votes отсутствуют)")
            else:
                a_weight, b_weight = Decimal("0.7"), Decimal("0.3")
                log("  • Вес формулы: A=0.7 (FanPoints), B=0.3 (Votes)")

            # Подсчёт весов по пользователям
            total_weight_sum = Decimal("0")
            user_weights = {}

            log("  • Детализация по пользователям:")
            for u in users:
                uid = u.id
                u_fp = Decimal(getattr(u, "fanpoints", 0) or 0)
                u_votes = Decimal(user_votes_cnt.get(uid, 0))
                # Ставки для логов (в итоговой формуле сейчас не участвуют, оставляем для аудита)
                u_stake = user_stakes.get(uid, Decimal("0"))

                part_fp = (u_fp / total_team_fanpoints) if total_team_fanpoints > 0 else Decimal("0")
                part_votes = (u_votes / Decimal(team_total_votes)) if team_total_votes > 0 else Decimal("0")
                weight = a_weight * part_fp + b_weight * part_votes

                log(f"    - user {uid}: FP={u_fp}, Votes={u_votes}, Stakes={u_stake} | "
                    f"part_fp={part_fp:.4f}, part_votes={part_votes:.4f}, weight={weight:.6f}")

                if weight > 0:
                    user_weights[uid] = weight
                    total_weight_sum += weight

            log(f"  • Σweights: {total_weight_sum:.6f}")

            if total_weight_sum == 0:
                log("  • Нет активности (весов) для распределения — приз команды не распределён.")
                continue

            # Распределение
            distributed = Decimal("0")
            receivers = 0

            for uid, w in user_weights.items():
                ratio = w / total_weight_sum
                reward = _q2(team_reward * ratio)
                if reward > 0:
                    CustomUser.objects.filter(id=uid).update(
                        balance_cached=F("balance_cached") + reward
                    )
                    distributed += reward
                    receivers += 1
                    log(f"      ➤ user {uid}: ratio={ratio:.4%}, reward={reward}")

            # Возможная дельта из-за округления — логируем
            delta = _q2(team_reward - distributed)
            log(f"  • Начислено пользователям: {distributed} (полагалось: {team_reward}, дельта округления: {delta})")
            log(f"  • Получателей: {receivers}")

    log("════════════════════════════════════════════════════════════")
    log("✅ РАЗДАЧА FANPOOL ЗАВЕРШЕНА")
    log("════════════════════════════════════════════════════════════")
