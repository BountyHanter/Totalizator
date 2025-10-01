from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from teams.models.teams import Team

User = get_user_model()  # Вот ключевой момент


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined',
                  'last_login', 'is_staff', 'is_superuser', 'balance_cached', 'favorite_team']


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    def get(self, request):
        user = request.user  # Получаем текущего авторизованного пользователя
        serializer = UserSerializer(user)
        return Response(serializer.data, status=200)

class FavoriteTeamUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        team_id = request.data.get("team_id")
        if not team_id:
            raise ValidationError("team_id обязателен.")

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            raise ValidationError("Команда не найдена.")

        request.user.favorite_team = team
        request.user.save(update_fields=["favorite_team"])

        return Response({
            "status": "ok",
            "favorite_team": team.id
        })