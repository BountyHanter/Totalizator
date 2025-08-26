from rest_framework_simplejwt.tokens import RefreshToken

def get_tokens_for_user(user):
    """
    Создать пару токенов (refresh + access) для юзера
    """
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
