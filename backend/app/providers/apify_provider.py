"""Enriquecimento via Apify: roda o actor de perfil e mapeia para `ProfileResult`.

Usa run assíncrono + sondagem porque o `run-sync` estoura o timeout em pedidos
grandes (ver POC na issue #12). Nada é inventado: sem dado = None, bio vazia
(`''`) vira NULL e `0` continua `0`.

`fetch_many` envia vários `usernames` por run (o actor aceita lista), reduzindo
latência e custo por pedido; o tamanho do lote fica em `services.py`.
"""
import os
import time
from datetime import datetime, timezone

import httpx

from .base import ProfileResult

API = "https://api.apify.com/v2"
RUN_TIMEOUT_SECS = 240   # teto por run; pedido grande continua nas retentativas


class _RateLimited(Exception):
    """A Apify recusou por limite (HTTP 429): o chamador decide o retry."""


def _now():
    return datetime.now(timezone.utc)


def _int_or_none(v):
    return None if v is None else int(v)


def _is_soft_limit(exc):
    """Cancelamentos do Celery (`SoftTimeLimitExceeded`) devem propagar, não virar `error`.

    Checagem pelo nome para não acoplar o provider ao Celery.
    """
    return type(exc).__name__ == "SoftTimeLimitExceeded"


def _to_result(item, source):
    """Mapeia um item do dataset para `ProfileResult` (regras validadas na POC)."""
    now = _now()
    if not item or item.get("error") == "not_found":
        return ProfileResult(status="not_found", source=source, fetched_at=now)
    status = "private" if item.get("private") is True else "ok"
    return ProfileResult(
        status=status,
        followers_count=_int_or_none(item.get("followersCount")),
        following_count=_int_or_none(item.get("followsCount")),
        bio=item.get("biography") or None,
        profile_url=item.get("url") or None,
        full_name=item.get("fullName") or None,
        external_url=item.get("externalUrl") or None,
        profile_pic_url=item.get("profilePicUrl") or None,
        posts_count=_int_or_none(item.get("postsCount")),
        category=item.get("businessCategoryName") or None,
        is_verified=item.get("verified"),
        is_business=item.get("isBusinessAccount"),
        source=source,
        fetched_at=now,
    )


class ApifyProvider:
    name = "apify"

    def __init__(self, token=None, actor_id=None, timeout_secs=RUN_TIMEOUT_SECS):
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise ValueError("APIFY_TOKEN não configurado")
        raw = actor_id or os.getenv("APIFY_ACTOR_ID", "apify/instagram-profile-scraper")
        self.actor_id = raw.replace("/", "~")
        self.timeout_secs = timeout_secs
        self._request = httpx.request   # ponto de troca nos testes
        self._sleep = time.sleep        # ponto de troca nos testes

    def fetch(self, username: str) -> ProfileResult:
        try:
            items = self._scrape([username])
            return _to_result(items[0] if items else {}, self.name)
        except _RateLimited:
            return ProfileResult(status="rate_limited", source=self.name, fetched_at=_now())
        except Exception as exc:
            if _is_soft_limit(exc):
                raise
            return ProfileResult(status="error", source=self.name, fetched_at=_now())

    def fetch_many(self, usernames):
        """Enriquece vários perfis em um único run; devolve `{username: ProfileResult}`.

        Retorna `None` quando a Apify limita (HTTP 429) — o chamador reagenda.
        Perfil sem item no dataset vira `not_found`; falha/timeout do run marca
        todos os usernames como `error`.
        """
        usernames = list(usernames)
        if not usernames:
            return {}
        try:
            items = self._scrape(usernames)
        except _RateLimited:
            return None
        except Exception as exc:
            if _is_soft_limit(exc):
                raise
            return {u: ProfileResult(status="error", source=self.name, fetched_at=_now())
                    for u in usernames}
        by_user = {}
        for it in items:
            u = (it or {}).get("username")
            if u:
                by_user[str(u).lower()] = it
        return {u: _to_result(by_user.get(u.lower()), self.name) for u in usernames}

    def _scrape(self, usernames):
        """Roda o actor uma vez para uma lista de usernames e devolve os itens do dataset."""
        run = self._call("POST", f"/acts/{self.actor_id}/runs",
                         json={"usernames": list(usernames)})
        run_id = run["data"]["id"]
        dataset_id = run["data"]["defaultDatasetId"]
        deadline = time.monotonic() + self.timeout_secs
        while True:
            state = self._call("GET", f"/actor-runs/{run_id}")["data"]["status"]
            if state == "SUCCEEDED":
                break
            if state in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"run {run_id}: {state}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"run {run_id} estourou {self.timeout_secs}s")
            self._sleep(5)
        return self._call("GET", f"/datasets/{dataset_id}/items",
                          params={"format": "json", "clean": "1"})

    def _call(self, method, path, **kw):
        r = self._request(method, API + path,
                          headers={"Authorization": f"Bearer {self.token}"},
                          timeout=30, **kw)
        if r.status_code == 429:
            raise _RateLimited(path)
        r.raise_for_status()
        return r.json()
