import random
from django.core.management.base import BaseCommand
from games.models.rounds import Round
from games.models.matchs import Match
from teams.models.teams import Team

MAX_ROUNDS = 8
MATCHES_PER_ROUND = 10


class Command(BaseCommand):
    help = "Поддерживает до 8 будущих раундов (создаёт новые раунды и матчи)"

    def handle(self, *args, **options):
        future_cnt = Round.objects.exclude(status=Round.Status.FINISHED).count()
        need = max(0, MAX_ROUNDS - future_cnt)

        if need == 0:
            self.stdout.write("Достаточно раундов, новые не нужны.")
            return

        # создаём недостающие раунды
        new_rounds = [Round(status=Round.Status.WAITING) for _ in range(need)]
        Round.objects.bulk_create(new_rounds, batch_size=need)

        # достаём их обратно (bulk_create не проставляет id в списке)
        created_rounds = list(
            Round.objects.filter(status=Round.Status.WAITING).order_by("-id")[:need]
        )[::-1]

        teams = list(Team.objects.filter(is_active=True))
        if len(teams) < MATCHES_PER_ROUND * 2:
            self.stdout.write("Недостаточно активных команд для генерации матчей.")
            return

        for round_obj in created_rounds:
            random.shuffle(teams)
            selected = teams[: MATCHES_PER_ROUND * 2]

            matches = [
                Match(round=round_obj, team1=selected[i], team2=selected[i + 1])
                for i in range(0, len(selected), 2)
            ]
            Match.objects.bulk_create(matches, batch_size=MATCHES_PER_ROUND)

        self.stdout.write(f"Создано {need} раундов и по {MATCHES_PER_ROUND} матчей в каждом.")
