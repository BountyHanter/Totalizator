import logging

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@csrf_exempt
def get_csrf_token(request):
    # allowed_origins = [os.getenv("ALLOWED_ORIGIN")]
    # origin = request.META.get('HTTP_ORIGIN')
    # if origin not in allowed_origins:
    #     return JsonResponse({'error': 'Forbidden'}, status=403)

    response = JsonResponse({'csrfToken': get_token(request)})
    response.set_cookie('csrftoken', get_token(request))  # Установить CSRF-cookie вручную
    logger.info("Запрос CSRF", extra={'status': "success"})
    return response
