from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from teams.models.teams import Team


class FanPointsTableView(APIView):
    """
    Таблица FanPoints — показывает текущие фанпоинты всех команд.
    Используется для формирования посева в плей-офф.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        # === 1️⃣ Загружаем все команды с их фанпоинтами ===
        teams = Team.objects.all().values("id", "name", "fanpoints")

        # === 2️⃣ Сортируем ===
        #  • по фанпоинтам (по убыванию)
        #  • у кого 0 — по названию (чтобы не было каши)
        sorted_teams = sorted(
            teams,
            key=lambda t: (-t["fanpoints"], t["name"].lower())
        )

        # === 3️⃣ Пронумеровываем места (как в таблице на скрине) ===
        result = []
        for i, team in enumerate(sorted_teams, start=1):
            result.append({
                "position": i,
                "id": team["id"],
                "name": team["name"],
                "fanpoints": float(team["fanpoints"]),  # на фронт удобно в float
            })

        # === 4️⃣ Возвращаем ===
        return Response(result)
