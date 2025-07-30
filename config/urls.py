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
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from games.views.bet import bet
from games.views.index import index
from games.views.stats import stats_view, user_variants_partial, stats_round_partial
from users.views.register import register_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", index, name="index"),
    path("stats/", stats_view, name="stats"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="index"), name="logout"),

    path('register/', register_view, name='register'),

    path("bet/", bet, name="bet"),

    path("round/<int:round_id>/user-variants/", user_variants_partial, name="user_variants_partial"),

    path("stats/round/<int:round_id>/", stats_round_partial, name="stats_round_partial"),
    path("stats/round/<int:round_id>/variants/", user_variants_partial, name="user_variants_partial"),

]
