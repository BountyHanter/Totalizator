import logging

from django.utils.timezone import localtime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model

from config.utils.jwt_token import get_tokens_for_user
from config.utils.logging_templates import log_warning, log_info

logger = logging.getLogger(__name__)

User = get_user_model()


class UserLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # Проверим, что такой пользователь существует
        try:
            user_obj = User.objects.get(username=username)
            if not user_obj.is_active:
                log_warning(
                    action='Попытка входа',
                    message='Юзер деактивирован',
                    username=username
                )
                return Response({'error': 'Ваш аккаунт деактивирован. Обратитесь к администрации.'},
                                status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            log_warning(
                action='Попытка входа',
                message='Юзер не найден',
                username=username
            )
            return Response({'error': 'Неверный логин или пароль.'},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            log_info(
                action='Попытка входа',
                message='Успешный вход',
                username=username
            )

            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_joined": localtime(user.date_joined).isoformat(),
                "last_login": localtime(user.last_login).isoformat() if user.last_login else None,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "balance_cached": user.balance_cached
            }

            tokens = get_tokens_for_user(user)

            return Response({
                'message': 'Удачная авторизация.',
                "user_data": user_data,
                "tokens": tokens
            }, status=status.HTTP_200_OK)
        else:
            log_warning(
                action='Попытка входа',
                message='Неверный пароль',
                username=username
            )
            return Response({'error': 'Неверный логин или пароль.'},
                            status=status.HTTP_400_BAD_REQUEST)

class LogoutAPIView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.user.username if request.user.is_authenticated else 'Anonymous'
        log_info(
            action='Выход',
            message='JWT logout (токены клиент сам удаляет)',
            username=username
        )
        logger.info(
            "JWT logout",
            extra={"username": username, "action": 'logout', 'status': 'success'}
        )
        return Response({"detail": "Токены удалены на клиенте."}, status=status.HTTP_200_OK)
