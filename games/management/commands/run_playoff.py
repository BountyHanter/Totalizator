import time
from django.core.management.base import BaseCommand
from django.db import transaction

from games.management.commands.playoff.services.calculate_result import calculate_match_result
from games.management.commands.playoff.services.checks import stage1_prepare
from games.management.commands.playoff.services.create_playoff import stage2_create_playoff
from games.management.commands.playoff.services.distribute import distribute_fanpool
from games.models.playoff import PlayoffMatch

SLEEP_BETWEEN_ROUNDS = 60  # секунд между стадиями


class Command(BaseCommand):
    help = "Полный цикл плей-офф: подготовка, турнир, распределение фонда"

    def handle(self, *args, **options):
        self.stdout.write("🏁 Запуск полного цикла FanPool Playoff\n")

        # === Этап 1: проверки и подготовка ===
        ctx = stage1_prepare(self.stdout)
        if not ctx:
            self.stdout.write("⏹ Этап 1 не пройден — выход.\n")
            return

        # === Этап 2: создание турнира ===
        data = stage2_create_playoff(ctx, self.stdout)
        playoff = data.get("playoff")
        if not playoff:
            self.stdout.write("⏹ Плей-офф не создан — выход.\n")
            return

        self.stdout.write(f"✅ Турнир #{playoff.id} успешно создан.\n")

        # === Этап 3: матчи и стадии ===
        stage_num = 1
        while True:
            matches = list(PlayoffMatch.objects.filter(playoff=playoff, round_number=stage_num))
            if not matches:
                self.stdout.write(f"✅ Нет матчей для стадии {stage_num}. Завершение турнира.\n")
                break

            self.stdout.write(f"\n⚔️  СТАДИЯ #{stage_num} — матчей: {len(matches)}")

            # ждём 1 минуту, чтобы игроки успели проголосовать
            self.stdout.write("⏳ Ожидание 60 секунд для голосований...")
            time.sleep(SLEEP_BETWEEN_ROUNDS)

            winners = []
            for match in matches:
                winner = calculate_match_result(match)
                match.winner = winner
                match.status = PlayoffMatch.Status.FINISHED
                match.save(update_fields=["winner", "status"])
                winners.append(winner)
                self.stdout.write(f"   🏁 {match.team1} vs {match.team2} → победитель: {winner}")

            # создаём следующую стадию
            if len(winners) == 1:
                playoff.winner = winners[0]
                playoff.finished = True
                playoff.save(update_fields=["winner", "finished"])
                self.stdout.write(f"\n🎉 Победитель турнира: {winners[0]}")
                break

            self.stdout.write(f"➡️  Формируем следующую стадию ({len(winners)} команд)")
            with transaction.atomic():
                for i in range(0, len(winners), 2):
                    team1 = winners[i]
                    team2 = winners[i + 1] if i + 1 < len(winners) else None
                    is_bye = team2 is None
                    PlayoffMatch.objects.create(
                        playoff=playoff,
                        round_number=stage_num + 1,
                        team1=team1,
                        team2=team2,
                        is_bye=is_bye,
                        winner=team1 if is_bye else None,
                    )
            stage_num += 1

        # === Этап 4: распределение фонда ===
        self.stdout.write("\n💰 Этап 4 — распределение FanPool\n")
        distribute_fanpool(playoff, stdout=self.stdout)
        self.stdout.write("✅ Плей-офф полностью завершён.\n")
