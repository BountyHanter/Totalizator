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
    Ставит результаты всем матчам раунда.
    Если force_outcome указан — проставляет его во все матчи.
    Иначе:
      1. Берёт случайные исходы с random.org.
      2. Генерирует server_seed.
      3. Формирует commit-хэш = SHA256(seed + результаты).
      4. Сохраняет result, seed, seed_hash в Match.
    """
    matches = list(Match.objects.filter(round=round_obj))
    if not matches:
        return

    # 1️⃣ Получаем результаты (или фиксированные)
    if force_outcome:
        results = [force_outcome for _ in matches]
    else:
        try:
            results = _rnd_generate_results(len(matches))
        except Exception:
            results = [random.choice([Match.Outcome.WIN_1, Match.Outcome.DRAW, Match.Outcome.WIN_2])
                       for _ in matches]

    # 2️⃣ Генерируем сид и хэш коммита
    server_seed = secrets.token_hex(32)
    joined_results = ",".join(results)
    server_seed_hash = hashlib.sha256(f"{server_seed}:{joined_results}".encode()).hexdigest()

    # 3️⃣ Проставляем данные в каждую запись
    for m, r in zip(matches, results):
        m.result = r
        m.server_seed = server_seed
        m.server_seed_hash = server_seed_hash

    # 4️⃣ Массовое сохранение
    Match.objects.bulk_update(matches, ["result", "server_seed", "server_seed_hash"])
