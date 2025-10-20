from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError

from games.models.playoff import FanVote


class FanVoteView(APIView):
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

        # проверяем, участвует ли его команда в матче
        if fav_team not in [match.team1, match.team2]:
            raise ValidationError("Ваша команда не участвует в этом матче.")

        # создаём или обновляем голос
        vote, created = FanVote.objects.update_or_create(
            user=user, match=match,
            defaults={"team": fav_team, "strategy": strategy}
        )

        return Response({
            "status": "ok",
            "created": created,
            "strategy": vote.strategy
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
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
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
