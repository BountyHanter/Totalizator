import hashlib
import secrets
import time
import httpx
import random
from typing import List
from games.models.matchs import Match

RND_ENDPOINT = "https://api.random.org/json-rpc/4/invoke"
API_KEY = "39e0d208-742b-4c71-828e-5d59f4b19c1b"


class RandomOrgError(RuntimeError):
    pass


def _random_org_call(method: str, params: dict) -> List[int]:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": {"apiKey": API_KEY, **params},
        "id": int(time.time() * 1000),
    }
    with httpx.Client(timeout=10) as client:
        resp = client.post(RND_ENDPOINT, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise RandomOrgError(data["error"])
    return data["result"]["random"]["data"]


def _rnd_generate_results(n: int) -> List[str]:
    values = _random_org_call("generateIntegers", {"n": n, "min": 1, "max": 3, "replacement": True})
    mapping = {1: Match.Outcome.WIN_1, 2: Match.Outcome.DRAW, 3: Match.Outcome.WIN_2}
    return [mapping[v] for v in values]


def generate_results_for_round(round_obj, force_outcome: str | None = None):
    """
    Для каждого матча генерирует результат, seed и hash:
      hash = sha256(seed + ':' + result)
    """
    matches = list(Match.objects.filter(round=round_obj))
    if not matches:
        return

    # 1️⃣ Результаты
    if force_outcome:
        results = [force_outcome for _ in matches]
    else:
        try:
            results = _rnd_generate_results(len(matches))
        except Exception:
            results = [random.choice([Match.Outcome.WIN_1, Match.Outcome.DRAW, Match.Outcome.WIN_2])
                       for _ in matches]

    # 2️⃣ Генерируем хэш для каждого матча
    for m, r in zip(matches, results):
        m.result = r
        m.server_seed = secrets.token_hex(32)
        m.server_seed_hash = hashlib.sha256(f"{m.server_seed}:{r}".encode()).hexdigest()

    # 3️⃣ Сохраняем
    Match.objects.bulk_update(matches, ["result", "server_seed", "server_seed_hash"])