import time
from django.utils import timezone
from games.models.rounds import Round


SELECTION_DURATION = 180  # секунд


def start_selection(round_obj):
    now = timezone.now()
    round_obj.status = Round.Status.SELECTION
    round_obj.start_time = now
    round_obj.selection_end_time = now + timezone.timedelta(seconds=SELECTION_DURATION)
    round_obj.save(update_fields=["status", "start_time", "selection_end_time"])

    sleep_seconds = max(0, int((round_obj.selection_end_time - timezone.now()).total_seconds()))
    if sleep_seconds:
        time.sleep(sleep_seconds)


def start_calculation(round_obj):
    round_obj.status = Round.Status.CALCULATION
    round_obj.save(update_fields=["status"])
