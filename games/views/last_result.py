from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from games.models.matchs import Match
from games.models.playoff import Playoff


class TeamStatsView(APIView):
    """
    Возвращает текущую турнирную таблицу между началом последнего плей-оффа и текущим моментом.

    Для каждой команды считает:
      • количество сыгранных матчей
      • победы, ничьи, поражения
      • очки (3 / 1 / 0)
      • последние 3 результата ("W", "D", "L")
    """

    def get(self, request):
        # === 1️⃣ Находим последний начатый плей-офф ===
        # Если хотя бы один плей-офф был запущен, берём его (по убыванию id)
        last_playoff = Playoff.objects.filter(started=True).order_by("-id").first()

        # === 2️⃣ Определяем, с какого момента брать матчи ===
        if last_playoff and last_playoff.start_round:
            # Если найден начатый плей-офф — берём все матчи после стартового раунда этого плей-оффа
            start_round_id = last_playoff.start_round.id
            matches = Match.objects.filter(round_id__gt=start_round_id)
        else:
            # Если плей-оффов нет вообще — просто берём все сыгранные матчи
            matches = Match.objects.all()

        # === 3️⃣ Проверяем, есть ли вообще матчи для анализа ===
        if not matches.exists():
            # Возвращаем понятное сообщение, а не пустую таблицу
            return Response(
                {"detail": "Нет сыгранных матчей для расчёта статистики."},
                status=status.HTTP_200_OK,
            )

        # === 4️⃣ Собираем статистику по каждой команде ===
        stats = {}

        for match in matches:
            # Пропускаем матчи без результата
            if not match.team1 or not match.team2 or not match.result:
                continue

            # Убедимся, что обе команды есть в словаре
            for team in [match.team1, match.team2]:
                if team.id not in stats:
                    stats[team.id] = {
                        "id": team.id,
                        "name": team.name,
                        "games": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "last_results": [],
                    }

            # === 4️⃣ Обновляем статистику ===
            t1, t2 = match.team1, match.team2
            stats[t1.id]["games"] += 1
            stats[t2.id]["games"] += 1

            # результат хранится как "1" / "2" / "X"
            if match.result == "1":  # победа team1
                stats[t1.id]["wins"] += 1
                stats[t2.id]["losses"] += 1
                stats[t1.id]["last_results"].append("W")
                stats[t2.id]["last_results"].append("L")

            elif match.result == "2":  # победа team2
                stats[t1.id]["losses"] += 1
                stats[t2.id]["wins"] += 1
                stats[t1.id]["last_results"].append("L")
                stats[t2.id]["last_results"].append("W")

            elif match.result == "X":  # ничья
                stats[t1.id]["draws"] += 1
                stats[t2.id]["draws"] += 1
                stats[t1.id]["last_results"].append("D")
                stats[t2.id]["last_results"].append("D")

        # === 5️⃣ Подсчитываем очки и ограничиваем последние 3 результата ===
        for team_data in stats.values():
            team_data["points"] = team_data["wins"] * 3 + team_data["draws"]
            # берём только последние 3 результата, в обратном порядке (сначала свежие)
            team_data["last_results"] = team_data["last_results"][-3:][::-1]

        # === 6️⃣ Сортируем таблицу по очкам и победам ===
        sorted_teams = sorted(
            stats.values(),
            key=lambda x: (-x["points"], -x["wins"], x["name"].lower())
        )

        # === 7️⃣ Возвращаем результат ===
        return Response(sorted_teams)
