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
        # === 1️⃣ Загружаем все активные команды ===
        # Берём queryset, чтобы можно было обращаться к avatar_url (оно не работает через .values())
        teams = Team.objects.filter(is_active=True)

        # === 2️⃣ Сортируем команды ===
        #  • по фанпоинтам (по убыванию)
        #  • у кого 0 — по названию (чтобы не было хаоса в конце)
        sorted_teams = sorted(
            teams,
            key=lambda t: (-t.fanpoints, t.name.lower())
        )

        # === 3️⃣ Формируем результат с местами и аватарками ===
        result = []
        for i, team in enumerate(sorted_teams, start=1):
            result.append({
                "position": i,                      # место в таблице
                "id": team.id,                      # id команды
                "name": team.name,                  # название
                "fanpoints": float(team.fanpoints), # фанпоинты в виде float для фронта
                "avatar": team.avatar_url,          # URL аватарки (может быть None)
            })

        # === 4️⃣ Возвращаем результат ===
        return Response(result)