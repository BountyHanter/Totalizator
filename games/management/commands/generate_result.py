import time
import httpx
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand

from games.models.rounds import Round
from games.models.matchs import Match


RND_ENDPOINT = "https://api.random.org/json-rpc/4/invoke"


class RandomOrgError(RuntimeError):
    pass


def random_org_call(method: str, params: dict) -> List:
    """Вызов RANDOM.ORG JSON-RPC через httpx."""
    api_key = "39e0d208-742b-4c71-828e-5d59f4b19c1b"
    if not api_key:
        raise RandomOrgError("RANDOM_ORG_API_KEY не задан в settings")

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": {"apiKey": api_key, **params},
        "id": int(time.time() * 1000),
    }

    with httpx.Client(timeout=10) as client:
        resp = client.post(RND_ENDPOINT, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise RandomOrgError(f"RANDOM.ORG error: {data['error']}")

    return data["result"]["random"]["data"]


def rnd_generate_results(n: int) -> List[str]:
    """
    Генерируем n чисел 1..3 и маппим:
      1 → '1', 2 → 'X', 3 → '2'
    """
    values = random_org_call("generateIntegers", {"n": n, "min": 1, "max": 3, "replacement": True})
    print(values)
    mapping = {1: Match.Outcome.WIN_1, 2: Match.Outcome.DRAW, 3: Match.Outcome.WIN_2}
    return [mapping[v] for v in values]


class Command(BaseCommand):
    help = "Генерация результатов матчей текущего CALCULATION-раунда через RANDOM.ORG"

    def handle(self, *args, **options):
        round_obj = Round.objects.filter(status=Round.Status.CALCULATION).order_by("id").first()
        if not round_obj:
            self.stdout.write("Нет раунда в статусе CALCULATION")
            return

        matches = list(Match.objects.filter(round=round_obj).only("id", "result"))
        if not matches:
            self.stdout.write(f"У раунда {round_obj.id} нет матчей")
            return

        try:
            results = rnd_generate_results(len(matches))
        except Exception as e:
            self.stdout.write(f"Ошибка RANDOM.ORG, fallback на random: {e}")
            import random
            results = [random.choice([Match.Outcome.WIN_1, Match.Outcome.DRAW, Match.Outcome.WIN_2]) for _ in matches]

        # Проставляем результаты
        for m, r in zip(matches, results):
            m.result = r

        Match.objects.bulk_update(matches, ["result"])

        self.stdout.write(f"Сгенерированы результаты для {len(matches)} матчей раунда {round_obj.id}.")
