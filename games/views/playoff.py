from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError

from games.models.playoff import FanVote



class FanVoteView(APIView):
    """
    Пользователь голосует за свою команду в конкретном матче.
    Один голос на матч.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        match_id = request.data.get("match_id")
        strategy = request.data.get("strategy")

        if not match_id or not strategy:
            raise ValidationError("Не переданы match_id или strategy.")

        try:
            match = PlayoffMatch.objects.get(id=match_id)
        except PlayoffMatch.DoesNotExist:
            raise ValidationError("Матч не найден.")

        user = request.user
        fav_team = user.favorite_team
        if not fav_team:
            raise ValidationError("Сначала выберите любимую команду.")

        # проверяем, участвует ли любимая команда
        if fav_team not in [match.team1, match.team2]:
            raise ValidationError("Ваша команда не участвует в этом матче.")

        # проверяем, голосовал ли уже
        if FanVote.objects.filter(user=user, match=match).exists():
            raise ValidationError("Вы уже голосовали в этом матче.")

        # проверяем стратегию
        valid_strategies = [choice[0] for choice in FanVote.Strategy.choices]
        if strategy not in valid_strategies:
            raise ValidationError(f"Недопустимая стратегия. Доступные: {', '.join(valid_strategies)}.")

        # создаём голос
        FanVote.objects.create(
            user=user,
            match=match,
            team=fav_team,
            strategy=strategy
        )

        return Response({
            "status": "ok",
            "team": fav_team.name,
            "strategy": strategy,
        })

class FanVoteCountView(APIView):
    """
    Возвращает количество голосов за указанную стратегию в конкретном матче.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        match_id = request.query_params.get("match_id")
        strategy = request.query_params.get("strategy")

        if not match_id or not strategy:
            raise ValidationError("Не переданы match_id или strategy.")

        try:
            match = PlayoffMatch.objects.get(id=match_id)
        except PlayoffMatch.DoesNotExist:
            raise ValidationError("Матч не найден.")

        # Проверяем корректность стратегии
        valid_strategies = [choice[0] for choice in FanVote.Strategy.choices]
        if strategy not in valid_strategies:
            raise ValidationError({
                "detail": f"Недопустимая стратегия '{strategy}'.",
                "available_strategies": {
                    key: label for key, label in FanVote.Strategy.choices
                }
            })

        # Считаем количество голосов
        count = FanVote.objects.filter(match=match, strategy=strategy).count()

        return Response({
            "match_id": match.id,
            "strategy": strategy,
            "count": count
        })

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from games.models.playoff import Playoff, PlayoffMatch


STAGE_NAMES = {
    1: "1/16 финала",
    2: "1/8 финала",
    3: "1/4 финала",
    4: "1/2 финала",
    5: "Финал"
}


class PlayoffBracketView(APIView):
    """
    Возвращает текущую турнирную сетку плей-офф:
    стадии, матчи, участников и победителей.
    """

    permission_classes = [AllowAny]
    def get(self, request):
        playoff = Playoff.objects.order_by("-created_at").first()
        if not playoff:
            raise NotFound("Плей-офф ещё не проводился.")

        matches = (
            PlayoffMatch.objects
            .filter(playoff=playoff)
            .select_related("team1", "team2", "winner")
            .order_by("round_number", "id")
        )

        if not matches.exists():
            return Response({"detail": "Нет матчей в текущем плей-офф."})

        bracket = {}
        for m in matches:
            stage = m.stage_slots
            if stage not in bracket:
                bracket[stage] = {
                    "stage_slots": stage,
                    "stage_name": m.stage_label,
                    "matches": []
                }

            bracket[stage]["matches"].append({
                "id": m.id,
                "team1": m.team1.name if m.team1 else None,
                "team2": m.team2.name if m.team2 else None,
                "winner": m.winner.name if m.winner else None,
                "status": m.status,
                "is_bye": m.is_bye,
            })

        # преобразуем в список по убыванию стадий (от 16 → 8 → 4 → 2)
        result = list(sorted(bracket.values(), key=lambda x: -x["stage_slots"]))

        return Response({
            "playoff_id": playoff.id,
            "winner": playoff.winner.name if playoff.winner else None,
            "finished": playoff.finished,
            "stages": result
        })


from rest_framework.views import APIView
from games.models.rounds import Round
from games.models.fanfool import FanPool

ROUND_DURATION = 90  # секунд


class NextPlayoffTimerView(APIView):
    """
    Возвращает время (в секундах) до следующего запуска плей-офф.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        pool = FanPool.get_solo()
        if not pool:
            raise NotFound("FanPool не найден.")

        current_round = (
            Round.objects.filter(status=Round.Status.SELECTION)
            .order_by("-id")
            .first()
        )
        if not current_round:
            raise NotFound("Активный раунд не найден.")

        remainder = current_round.id % pool.rounds_interval
        rounds_left = pool.rounds_interval - remainder if remainder != 0 else 0

        seconds_left = rounds_left * ROUND_DURATION
        return Response(seconds_left)


from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from games.models.playoff import Playoff, PlayoffMatch




class MyPlayoffMatchView(APIView):
    """
    Возвращает текущий матч (status=VOTING), где участвует любимая команда пользователя.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        favorite_team = getattr(user, "favorite_team", None)

        if not favorite_team:
            raise NotFound("У пользователя не указана любимая команда.")

        # Находим последний активный или начатый плей-офф
        playoff = (
            Playoff.objects.filter(started=True, finished=False)
            .order_by("-id")
            .first()
        )
        if not playoff:
            raise NotFound("Активный плей-офф не найден.")

        # Ищем матч в стадии голосования (VOTING) с участием любимой команды
        match = (
            PlayoffMatch.objects
            .filter(
                playoff=playoff,
                status=PlayoffMatch.Status.VOTING
            )
            .filter(Q(team1=favorite_team) | Q(team2=favorite_team))
            .select_related("team1", "team2", "winner")
            .first()
        )

        if not match:
            raise NotFound("Ваша команда сейчас не участвует в голосовании плей-офф.")

        return Response({
            "id": match.id,
            "stage_label": match.stage_label,
            "status": match.status,
            "team1": {
                "id": match.team1.id,
                "name": match.team1.name,
                "avatar": match.team1.avatar_url,
            } if match.team1 else None,
            "team2": {
                "id": match.team2.id if match.team2 else None,
                "name": match.team2.name if match.team2 else None,
                "avatar": match.team2.avatar_url if match.team2 else None,
            } if match.team2 else None,
            "favorite_team": {
                "id": favorite_team.id,
                "name": favorite_team.name,
            },
        })

class MyVoteInMatchView(APIView):
    """
    Возвращает только выбор пользователя (FanVote) по конкретному матчу.
    Требуется match_id в query параметре (?match_id=...).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        match_id = request.query_params.get("match_id")

        if not match_id:
            raise ValidationError("Не передан match_id.")

        try:
            match = PlayoffMatch.objects.get(id=match_id)
        except PlayoffMatch.DoesNotExist:
            raise NotFound("Матч не найден.")

        vote = FanVote.objects.filter(user=user, match=match).select_related("team").first()
        if not vote:
            raise NotFound("Пользователь ещё не голосовал в этом матче.")

        return Response({
            "strategy": vote.strategy,
        })