from django.core.management.base import BaseCommand
from django.db import transaction
from games.management.commands.playoff.services.calculate_result import calculate_match_result
from games.management.commands.playoff.services.checks import stage1_prepare
from games.management.commands.playoff.services.create_playoff import stage2_create_playoff
from games.management.commands.playoff.services.distribute import distribute_fanpool
from games.models.playoff import Playoff, PlayoffMatch


class Command(BaseCommand):
    help = "Пошаговый цикл FanPool Playoff с очисткой незавершённых турниров"

    def cleanup_unfinished_playoffs(self):
        """Закрывает все незавершённые турниры и матчи"""
        unfinished = Playoff.objects.filter(finished=False)

        if not unfinished.exists():
            self.stdout.write("🧹 Незавершённых турниров не найдено.\n")
            return

        self.stdout.write(f"🧹 Найдено {unfinished.count()} незавершённых турниров. Завершаем их...\n")

        for playoff in unfinished:
            matches = PlayoffMatch.objects.filter(playoff=playoff)
            if not matches.exists():
                self.stdout.write(f"⚠️ Турнир #{playoff.id} без матчей — просто помечаем завершённым.")
                playoff.finished = True
                playoff.save(update_fields=["finished"])
                continue

            # Завершаем все активные матчи (PENDING/VOTING)
            active_matches = matches.filter(
                status__in=[PlayoffMatch.Status.PENDING, PlayoffMatch.Status.VOTING]
            )

            if active_matches.exists():
                self.stdout.write(f"⚙️ Завершаем {active_matches.count()} активных матчей турнира #{playoff.id}...")
                for m in active_matches:
                    if not m.winner:
                        m.winner = m.team1 or m.team2  # подстраховка, чтобы не оставить без победителя
                    m.status = PlayoffMatch.Status.FINISHED
                    m.save(update_fields=["winner", "status"])

            # Определяем финального победителя по последнему матчу
            last_match = matches.order_by("-id").first()
            playoff.winner = last_match.winner if last_match and last_match.winner else None
            playoff.finished = True
            playoff.save(update_fields=["winner", "finished"])

            winner_name = playoff.winner.name if playoff.winner else "не определён"
            self.stdout.write(f"✅ Турнир #{playoff.id} закрыт. Победитель: {winner_name}")

        self.stdout.write("✅ Все незавершённые турниры и матчи успешно закрыты.\n")

    def handle(self, *args, **options):
        self.stdout.write("🏁 Запуск пошагового цикла FanPool Playoff\n")

        # === Очистка незавершённых турниров ===
        self.cleanup_unfinished_playoffs()

        # === Этап 1: проверка и подготовка ===
        # Здесь формируется контекст с командами, фондами и бонусами.
        ctx = stage1_prepare(self.stdout)
        if not ctx:
            self.stdout.write("⏹ Этап 1 не пройден — выход.\n")
            return

        # === Этап 2: создание турнира ===
        # Генерируются пары первой стадии и создаются PlayoffMatch.
        data = stage2_create_playoff(ctx, self.stdout)
        playoff = data.get("playoff")
        if not playoff:
            self.stdout.write("⏹ Плей-офф не создан — выход.\n")
            return
        self.stdout.write(f"✅ Турнир #{playoff.id} успешно создан.\n")

        # === Этап 3: стадийный цикл ===
        # Определяем первую стадию по максимальному stage_slots (например, 16, 8 и т.д.)
        first_stage = PlayoffMatch.objects.filter(playoff=playoff).order_by('-stage_slots').first()
        if not first_stage:
            self.stdout.write("❌ Не удалось определить первую стадию (нет матчей).")
            return

        stage_slots = first_stage.stage_slots

        while stage_slots >= 1:
            # Получаем все матчи текущей стадии
            matches = list(PlayoffMatch.objects.filter(playoff=playoff, stage_slots=stage_slots))
            if not matches:
                self.stdout.write(f"✅ Нет матчей для стадии {stage_slots}. Завершение турнира.\n")
                break

            self.stdout.write(f"\n⚔️  СТАДИЯ {stage_slots} → матчей: {len(matches)}")

            # === Расчёт результатов матчей ===
            winners = []
            for match in matches:
                winner = calculate_match_result(match)
                match.winner = winner
                match.status = PlayoffMatch.Status.FINISHED
                match.save(update_fields=["winner", "status"])
                winners.append(winner)
                self.stdout.write(f"   🏁 {match.team1} vs {match.team2} → победитель: {winner}")

            # === Если остался один победитель — конец турнира ===
            if len(winners) == 1:
                playoff.winner = winners[0]
                playoff.finished = True
                playoff.save(update_fields=["winner", "finished"])
                self.stdout.write(f"\n🎉 Победитель турнира: {winners[0]}")
                break

            # === Формируем следующую стадию ===
            # stage_slots всегда уменьшается в 2 раза, но не ниже 1
            next_stage = max(stage_slots // 2, 1)

            # 👇 Исправление логики для корректного отображения 1/4, 1/2, финала
            # Если осталось 2 команды — это полуфинал (1/2)
            if len(winners) == 2:
                next_stage = 2
            # Если 1 — это финал (stage_slots = 1)
            elif len(winners) == 1:
                next_stage = 1

            self.stdout.write(f"▶ Формируем следующую стадию ({len(winners)} → {next_stage})...\n")

            # === Создаём новые матчи ===
            with transaction.atomic():
                for i in range(0, len(winners), 2):
                    team1 = winners[i]
                    team2 = winners[i + 1] if i + 1 < len(winners) else None
                    is_bye = team2 is None

                    PlayoffMatch.objects.create(
                        playoff=playoff,
                        stage_slots=next_stage,           # сколько команд в стадии
                        pair_index=i // 2 + 1,            # порядковый номер пары
                        team1=team1,
                        team2=team2,
                        seed1=i + 1,
                        seed2=i + 2 if team2 else None,
                        is_bye=is_bye,
                        winner=team1 if is_bye else None,  # если автопроход
                        status=(
                            PlayoffMatch.Status.VOTING
                            if not is_bye
                            else PlayoffMatch.Status.FINISHED
                        ),
                    )

            # Переходим к следующему этапу
            stage_slots = next_stage

        # === Этап 4: распределение фонда ===
        # Здесь происходит расчёт наград и обнуление фонда.
        distribute_fanpool(playoff, stdout=self.stdout)
        self.stdout.write("✅ Плей-офф полностью завершён.\n")
