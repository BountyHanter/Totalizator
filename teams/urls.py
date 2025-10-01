from django.urls import path

from teams.views import TeamListView

urlpatterns = [
    path("teams/", TeamListView.as_view()),

]
