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
      • аватар (avatar_url)
    """

    def get(self, request):
        # === 1️⃣ Находим последний начатый плей-офф ===
        last_playoff = (
            Playoff.objects.filter(started=True)
            .order_by("-id")
            .select_related("start_round")
            .first()
        )

        # === 2️⃣ Определяем набор матчей ===
        if last_playoff and last_playoff.start_round:
            start_round_id = last_playoff.start_round_id
            matches = Match.objects.filter(
                round_id__gt=start_round_id, result__in=["1", "2", "X"]
            )
        else:
            matches = Match.objects.filter(result__in=["1", "2", "X"])

        # Предзагружаем связанные команды для ускорения
        matches = matches.select_related("team1", "team2").only(
            "id",
            "result",
            "team1__id", "team1__name", "team1__avatar",
            "team2__id", "team2__name", "team2__avatar",
        )

        # === 3️⃣ Проверяем, есть ли матчи ===
        if not matches.exists():
            return Response(
                {"detail": "Нет сыгранных матчей для расчёта статистики."},
                status=status.HTTP_200_OK,
            )

        # === 4️⃣ Собираем статистику ===
        stats = {}

        for match in matches.iterator():
            t1, t2 = match.team1, match.team2

            for team in [t1, t2]:
                if team.id not in stats:
                    stats[team.id] = {
                        "id": team.id,
                        "name": team.name,
                        "avatar": team.avatar_url,
                        "games": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "last_results": [],
                    }

            stats[t1.id]["games"] += 1
            stats[t2.id]["games"] += 1

            # Обновляем по результату
            if match.result == "1":
                stats[t1.id]["wins"] += 1
                stats[t2.id]["losses"] += 1
                stats[t1.id]["last_results"].append("W")
                stats[t2.id]["last_results"].append("L")

            elif match.result == "2":
                stats[t1.id]["losses"] += 1
                stats[t2.id]["wins"] += 1
                stats[t1.id]["last_results"].append("L")
                stats[t2.id]["last_results"].append("W")

            elif match.result == "X":
                stats[t1.id]["draws"] += 1
                stats[t2.id]["draws"] += 1
                stats[t1.id]["last_results"].append("D")
                stats[t2.id]["last_results"].append("D")

        # === 5️⃣ Подсчитываем очки и последние 3 результата ===
        for team_data in stats.values():
            team_data["points"] = team_data["wins"] * 3 + team_data["draws"]
            team_data["last_results"] = team_data["last_results"][-3:][::-1]

        # === 6️⃣ Сортировка ===
        sorted_teams = sorted(
            stats.values(),
            key=lambda x: (-x["points"], -x["wins"], x["name"].lower()),
        )

        # === 7️⃣ Возврат результата ===
        return Response(sorted_teams, status=status.HTTP_200_OK)
