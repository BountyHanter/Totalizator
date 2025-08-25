"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from config.utils.get_csrf import get_csrf_token
from users.views.auth import UserLoginAPIView, LogoutAPIView
from users.views.register import AutoRegisterLoginAPIView
from users.views.user_Info import UserProfileAPIView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/login/', UserLoginAPIView.as_view()),
    path('auth/logout/', LogoutAPIView.as_view()),
    path('auth/register/', AutoRegisterLoginAPIView.as_view()),

    path('api/v1/csrf/', get_csrf_token),
    path('api/v1/', include([
        path('games/', include('games.urls')),
        path('profile/', UserProfileAPIView.as_view()),

    ])),

]
