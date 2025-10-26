from django.core.management.base import BaseCommand
import random
from decimal import Decimal
from django.contrib.auth import get_user_model

from games.models.matchs import Match
from games.models.rounds import Round
from games.models.bets import BetCoupon, BetVariant, SelectedOutcome
from games.models.payout import PayoutScheme
from teams.models.teams import Team


class Command(BaseCommand):
    help = "Симулирует ставки фанатов в активном раунде"

    def handle(self, *args, **options):
        BET_AMOUNT = Decimal("100")
        OUTCOMES = ["win1", "draw", "win2"]
        team_users_map = {
            9: list(range(218, 238)),  # AS Roma
            26: list(range(278, 298)),  # AFC Ajax
        }

        User = get_user_model()
        global teams_betted
        if "teams_betted" not in globals():
            teams_betted = set()

        round_ = Round.objects.filter(status=Round.Status.SELECTION).order_by("-id").first()
        if not round_:
            self.stdout.write("❌ Нет активного раунда (status=selection)")
            return

        self.stdout.write(f"🎯 Активный раунд: {round_.id}")
        matches = list(Match.objects.filter(round=round_))
        if not matches:
            self.stdout.write("❌ Нет матчей в текущем раунде")
            return

        self.stdout.write(f"⚔️ Матчей в раунде: {len(matches)}")
        active_team_ids = set()
        for m in matches:
            if m.team1_id in team_users_map:
                active_team_ids.add(m.team1_id)
            if m.team2_id in team_users_map:
                active_team_ids.add(m.team2_id)
        self.stdout.write(f"🧩 Найдено активных команд из твоего списка: {len(active_team_ids)}")

        scheme = PayoutScheme.objects.filter(active=True).first()
        if not scheme:
            scheme = PayoutScheme.objects.create(name="Default", active=True)
            self.stdout.write("ℹ️ Создана схема выплат по умолчанию")

        for team_id in active_team_ids:
            if team_id in teams_betted:
                self.stdout.write(f"⏭️ Команда {team_id} уже ставила — пропускаем")
                continue

            team = Team.objects.get(id=team_id)
            user_ids = team_users_map[team_id]
            self.stdout.write(f"\n⚽ Команда {team.name} ({team.id}) — фанатов: {len(user_ids)}")

            for uid in user_ids:
                user = User.objects.get(id=uid)
                if user.balance_cached < BET_AMOUNT:
                    continue

                coupon = BetCoupon.objects.create(
                    user=user,
                    round=round_,
                    amount_total=BET_AMOUNT,
                    payout_scheme=scheme,
                    num_variants=1
                )
                variant = BetVariant.objects.create(coupon=coupon)
                match = random.choice(matches)
                outcome = random.choice(OUTCOMES)
                SelectedOutcome.objects.create(variant=variant, match=match, outcome=outcome)
                user.balance_cached -= BET_AMOUNT
                user.save(update_fields=["balance_cached"])

            teams_betted.add(team_id)
            self.stdout.write(f"✅ Ставки сделаны для команды {team.name}")

        remaining = set(team_users_map.keys()) - teams_betted
        if remaining:
            self.stdout.write("\n⏳ Остались команды без ставок:")
            for tid in remaining:
                t = Team.objects.get(id=tid)
                self.stdout.write(f" - {t.name} (ID {tid})")
        else:
            self.stdout.write("\n🎉 Все команды уже сделали ставки во всех активных раундах!")
