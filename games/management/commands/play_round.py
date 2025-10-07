from django.core.management import BaseCommand

from games.management.commands.services.matches_count import recompute_matched_counts
from games.management.commands.services.payouts import process_payouts
from games.management.commands.services.results import generate_results_for_round
from games.management.commands.services.rounds import start_selection, start_calculation
from games.models.matchs import Match
from games.models.rounds import Round


class Command(BaseCommand):
    help = "Симуляция одного игрового раунда от начала до завершения"

    def handle(self, *args, **options):
        round_obj = Round.objects.filter(status=Round.Status.WAITING).order_by("id").first()
        if not round_obj:
            self.stdout.write("Нет доступного раунда для симуляции")
            return

        # 1) стадия ставок
        start_selection(round_obj)

        # 2) стадия калькуляции
        start_calculation(round_obj)
        generate_results_for_round(round_obj)

        # 3) пересчитали matched_count у всех вариантов
        recompute_matched_counts(round_obj)

        # 4) выплаты и финализация
        process_payouts(round_obj)

        self.stdout.write(f"Раунд {round_obj.id} завершён")
