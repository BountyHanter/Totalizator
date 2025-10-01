from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from teams.models.teams import Team


class TeamSerializer(serializers.ModelSerializer):
    avatar_url = serializers.ReadOnlyField()

    class Meta:
        model = Team
        fields = ["id", "name", "country", "is_active", "avatar_url"]


class TeamListView(ListAPIView):
    serializer_class = TeamSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Team.objects.filter(is_active=True).order_by("name")