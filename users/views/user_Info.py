from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()  # Вот ключевой момент


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'last_login', 'is_staff', 'is_superuser']


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    def get(self, request):
        user = request.user  # Получаем текущего авторизованного пользователя
        serializer = UserSerializer(user)
        return Response(serializer.data, status=200)
