from django.core.management.base import BaseCommand
from django.db import transaction
from games.management.commands.playoff.services.calculate_result import calculate_match_result
from games.management.commands.playoff.services.checks import stage1_prepare
from games.management.commands.playoff.services.create_playoff import stage2_create_playoff
from games.management.commands.playoff.services.distribute import distribute_fanpool
from games.models.playoff import PlayoffMatch, Playoff


class Command(BaseCommand):
    help = "Пошаговый цикл плей-офф с ожиданием подтверждения"

    def cleanup_unfinished_playoffs(self):
        unfinished = Playoff.objects.filter(finished=False)
        if not unfinished.exists():
            self.stdout.write("🧹 Незавершённых турниров не найдено.")
            return

        self.stdout.write(f"🧹 Найдено {unfinished.count()} незавершённых турниров. Завершаем их...")

        for playoff in unfinished:
            matches = PlayoffMatch.objects.filter(playoff=playoff, status__in=[
                PlayoffMatch.Status.PENDING,
                PlayoffMatch.Status.VOTING
            ])
            for m in matches:
                if not m.winner:
                    # если победитель не определён, ставим победу первой команде (или None)
                    m.winner = m.team1 or m.team2
                m.status = PlayoffMatch.Status.FINISHED
                m.save(update_fields=["winner", "status"])

            playoff.finished = True
            if not playoff.winner and matches.exists():
                playoff.winner = matches.last().winner
            playoff.save(update_fields=["winner", "finished"])

        self.stdout.write("✅ Все незавершённые турниры и матчи были закрыты.\n")

    def handle(self, *args, **options):
        self.stdout.write("🏁 Запуск пошагового цикла FanPool Playoff\n")

        # === Очистка мусора ===
        self.cleanup_unfinished_playoffs()

        input("▶ Нажми Enter, чтобы выполнить ЭТАП 1 (проверка и подготовка)...")
        ctx = stage1_prepare(self.stdout)
        if not ctx:
            self.stdout.write("⏹ Этап 1 не пройден — выход.\n")
            return

        input("▶ Нажми Enter, чтобы выполнить ЭТАП 2 (создание турнира)...")
        data = stage2_create_playoff(ctx, self.stdout)
        playoff = data.get("playoff")
        if not playoff:
            self.stdout.write("⏹ Плей-офф не создан — выход.\n")
            return
        self.stdout.write(f"✅ Турнир #{playoff.id} успешно создан.\n")

        stage_num = 1
        while True:
            matches = list(PlayoffMatch.objects.filter(playoff=playoff, round_number=stage_num))
            if not matches:
                self.stdout.write(f"✅ Нет матчей для стадии {stage_num}. Завершение турнира.\n")
                break

            self.stdout.write(f"\n⚔️  СТАДИЯ #{stage_num} — матчей: {len(matches)}")
            input(f"▶ Нажми Enter, чтобы рассчитать результаты стадии #{stage_num}...")

            winners = []
            for match in matches:
                winner = calculate_match_result(match)
                match.winner = winner
                match.status = PlayoffMatch.Status.FINISHED
                match.save(update_fields=["winner", "status"])
                winners.append(winner)
                self.stdout.write(f"   🏁 {match.team1} vs {match.team2} → победитель: {winner}")

            if len(winners) == 1:
                playoff.winner = winners[0]
                playoff.finished = True
                playoff.save(update_fields=["winner", "finished"])
                self.stdout.write(f"\n🎉 Победитель турнира: {winners[0]}")
                break

            input(f"▶ Нажми Enter, чтобы сформировать следующую стадию ({len(winners)} команд)...")
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

        input("\n▶ Нажми Enter, чтобы выполнить ЭТАП 4 (распределение фонда)...")
        distribute_fanpool(playoff, stdout=self.stdout)
        self.stdout.write("✅ Плей-офф полностью завершён.\n")
