import random
import time
import uuid

from django.core.management.base import BaseCommand

from games.management.commands.logger import log
from games.models.matchs import Match
from games.models.rounds import Round
from teams.models.teams import Team

MAX_ROUNDS = 8
NEW_ROUNDS = []

class Command(BaseCommand):
    help = "Генерация будущих раундов (до 8 штук вперёд)"

    def handle(self, *args, **options):
        generate_rounds()

        for round in NEW_ROUNDS:
            generate_match(round)


def generate_rounds():
    # Считаем количество ещё не отыгравших (не FINISHED) раундов
    future_rounds_count = Round.objects.exclude(status=Round.Status.FINISHED).count()
    log.info(f"Активных/ожидающих раундов: {future_rounds_count}")

    # Берём последний по ID (т.е. последний созданный)
    last_round = Round.objects.order_by('-id').first()
    log.info(f"Последний раунд: {last_round}")

    for i in range(1, (MAX_ROUNDS - future_rounds_count) + 1):
        round = Round.objects.create(
            status=Round.Status.WAITING,
            game_hash=generate_uuid_hash()
        )

        NEW_ROUNDS.append(round)
        log.info(f"Создан раунд {i} (id={round.id})")


def generate_match(round: Round):
    teams = list(Team.objects.filter(is_active=True))
    random.shuffle(teams)

    if len(teams) < 2:
        log.warning("Недостаточно активных команд для создания матчей.")
        return

    # Обрезаем список до чётного количества
    if len(teams) % 2 != 0:
        teams = teams[:-1]

    for i in range(0, len(teams), 2):
        team1 = teams[i]
        team2 = teams[i + 1]

        Match.objects.create(
            round=round,
            team1=team1,
            team2=team2,
            result=generate_match_result()
        )


def generate_match_result() -> str:
    outcomes = [Match.Outcome.WIN_1, Match.Outcome.DRAW, Match.Outcome.WIN_2]
    weights = [34, 33, 33]  # 34% для одной из опций

    # Рандомно переставим веса, чтобы каждый раз разная опция была 34%
    random.shuffle(weights)

    # Выбираем результат с учётом рандомных весов
    result = random.choices(outcomes, weights=weights, k=1)[0]
    return result


def generate_uuid_hash():
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(time.time())).hex