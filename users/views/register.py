import secrets
import string
from django.contrib.auth import login as auth_login
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.timezone import localtime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.utils.logging_templates import log_warning, log_info

User = get_user_model()


def _gen_numeric_username(length: int = 10) -> str:
    # Только цифры
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def _gen_password(length: int = 16) -> str:
    # Безопасный пароль
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class AutoRegisterLoginAPIView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        # 1) Сгенерировать уникальный username (только цифры)
        for _ in range(20):
            username = _gen_numeric_username(10)
            if not User.objects.filter(username=username).exists():
                break
        else:
            log_warning(action="Авто-регистрация", message="Не удалось сгенерировать уникальный username")
            return Response({"error": "Попробуйте позже."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 2) Сгенерировать пароль
        password = _gen_password(16)

        # 3) Создать пользователя
        user = User(username=username)
        user.set_password(password)
        # Если у модели есть обязательные поля — заполни их здесь (email и т.п.)
        user.save()

        log_info(action="Авто-регистрация", message="Пользователь создан", username=username, user_id=user.id)

        # 4) Аутентифицировать и залогинить (создаст sessionid cookie)
        auth_user = authenticate(request, username=username, password=password)
        if auth_user is None or not auth_user.is_active:
            log_warning(action="Авто-логин", message="Не удалось аутентифицировать сразу после создания", username=username)
            return Response({"error": "Auth failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        auth_login(request, auth_user)
        log_info(action="Авто-логин", message="Успешный вход", username=username, user_id=user.id)

        # 5) Сформировать user_data как в твоей авторизации
        user = auth_user  # для краткости
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": getattr(user, "email", ""),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "date_joined": localtime(user.date_joined).isoformat(),
            "last_login": localtime(user.last_login).isoformat() if user.last_login else None,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "balance_cached": getattr(user, "balance_cached", 0),
        }

        # 6) Ответ + куки. sessionid выставится автоматически.
        # Положим CSRF, чтобы фронт мог сразу слать POST-ы с X-CSRFToken при сессионной аутентификации.
        resp = Response(
            {
                "message": "ok",
                "user_data": user_data,
            },
            status=status.HTTP_201_CREATED
        )
        csrf = get_token(request)
        resp.set_cookie("csrftoken", csrf, max_age=31449600, httponly=False, samesite="None", secure=True)
        return resp