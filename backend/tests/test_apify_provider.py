"""Provider Apify com HTTP mockado: valida o mapeamento descoberto na POC (#12).

Nenhum teste usa token real (`PROVIDER` segue `null` por padrão no CI).
"""
import httpx
import pytest

from app.providers import get_provider
from app.providers.apify_provider import ApifyProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)


def _provider(scenes, **kw):
    """Provider com `_request` fake; `scenes` mapeia trecho da URL -> resposta ou exceção."""
    p = ApifyProvider(token="fake", **kw)
    p._sleep = lambda s: None
    def fake(method, url, **kw):
        for needle, action in scenes.items():
            if needle in url:
                if isinstance(action, Exception):
                    raise action
                if callable(action):
                    return action()
                return action
        raise AssertionError(f"URL inesperada: {url}")
    p._request = fake
    return p


def _run_ok(statuses=("SUCCEEDED",), items=None):
    calls = {"n": 0}
    def poll():
        calls["n"] += 1
        return FakeResponse({"data": {"status": statuses[min(calls["n"] - 1, len(statuses) - 1)]}})
    return {
        "/runs": FakeResponse({"data": {"id": "run1", "defaultDatasetId": "ds1"}}),
        "actor-runs": poll,
        "datasets": FakeResponse(items if items is not None else []),
    }


def test_mapeia_perfil_ok():
    p = _provider(_run_ok(items=[{
        "username": "sony", "followersCount": 4327007, "followsCount": 840,
        "biography": "bio", "url": "https://www.instagram.com/sony",
        "private": False}]))
    r = p.fetch("sony")
    assert (r.status, r.followers_count, r.following_count, r.bio) == ("ok", 4327007, 840, "bio")
    assert (r.profile_url, r.source) == ("https://www.instagram.com/sony", "apify")
    assert r.fetched_at is not None


def test_privada_aproveita_contadores():
    p = _provider(_run_ok(items=[{
        "username": "a", "followersCount": 447, "followsCount": 674,
        "biography": "", "url": "https://www.instagram.com/a", "private": True}]))
    r = p.fetch("a")
    assert r.status == "private"
    assert (r.followers_count, r.following_count) == (447, 674)
    assert r.bio is None   # '' vira NULL, nunca string vazia


def test_zero_de_verdade_nao_vira_none():
    p = _provider(_run_ok(items=[{
        "username": "p", "followersCount": 0, "followsCount": 0,
        "biography": "", "url": "https://www.instagram.com/p", "private": False}]))
    r = p.fetch("p")
    assert (r.status, r.followers_count, r.following_count) == ("ok", 0, 0)


def test_inexistente_vira_not_found():
    p = _provider(_run_ok(items=[{
        "username": "x", "url": "https://www.instagram.com/x",
        "error": "not_found", "errorDescription": "Profile does not exist"}]))
    r = p.fetch("x")
    assert r.status == "not_found"
    assert r.followers_count is None and r.bio is None


def test_dataset_vazio_vira_not_found():
    assert _provider(_run_ok(items=[])).fetch("x").status == "not_found"


def test_429_vira_rate_limited():
    p = _provider({"/runs": FakeResponse({}, 429)})
    assert p.fetch("x").status == "rate_limited"


def test_run_falho_vira_error():
    p = _provider(_run_ok(statuses=("RUNNING", "FAILED")))
    assert p.fetch("x").status == "error"


def test_timeout_vira_error_sem_dormir():
    p = _provider(_run_ok(statuses=("RUNNING",)), timeout_secs=0)
    p._sleep = lambda s: pytest.fail("não deveria sondar após o teto")
    assert p.fetch("x").status == "error"


def test_sem_token_falha_explicita(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with pytest.raises(ValueError, match="APIFY_TOKEN"):
        ApifyProvider()


def test_get_provider_registra_apify_e_rejeita_desconhecido(monkeypatch):
    monkeypatch.setenv("PROVIDER", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "fake")
    assert get_provider().name == "apify"
    monkeypatch.setenv("PROVIDER", "outro")
    with pytest.raises(ValueError, match="desconhecido"):
        get_provider()


def test_enriquecimento_persiste_link_origem_data(env, monkeypatch):
    """O `run_enrichment` grava `profile_url/source/enriched_at` vindos do provider."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app import services
    from app.models import Profile
    from app.providers.base import ProfileResult
    from tests.helpers import make_zip, register, upload
    from tests.test_api import NEW, OLD

    client, Session, tmp = env
    h = register(client)
    p = tmp / "e.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[])
    oid = upload(client, p, h).json()["order_id"]

    quando = datetime(2026, 10, 16, tzinfo=timezone.utc)

    class FakeProvider:
        name = "fake"

        def fetch(self, username):
            return ProfileResult(status="ok", followers_count=10, following_count=5,
                                 bio="b", profile_url=f"https://www.instagram.com/{username}",
                                 source="fake", fetched_at=quando)

    monkeypatch.setattr(services, "get_provider", lambda: FakeProvider())
    assert services.run_enrichment(oid) == "done"
    with Session() as db:
        prof = db.scalar(select(Profile).where(Profile.username == "ana_silva"))
        assert prof.profile_url == "https://www.instagram.com/ana_silva"
        assert prof.enrich_source == "fake"
        # SQLite descarta o tz (no Postgres, TIMESTAMPTZ preserva)
        assert prof.enriched_at == quando.replace(tzinfo=None)


def test_cache_reusa_enriquecido_ha_menos_de_7_dias(env, monkeypatch):
    """Perfil 'ok' enriquecido há < 7 dias não é reconsultado (usa o do banco)."""
    from datetime import datetime, timezone

    from app import services
    from app.providers.base import ProfileResult
    from tests.helpers import make_zip, register, upload
    from tests.test_api import OLD

    client, Session, tmp = env
    h = register(client)
    p = tmp / "e.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[])

    calls = {"n": 0}
    class FakeProvider:
        name = "fake"
        def fetch(self, username):
            calls["n"] += 1
            return ProfileResult(status="ok", followers_count=10, following_count=5,
                                 bio="b", source="fake", fetched_at=datetime.now(timezone.utc))
    monkeypatch.setattr(services, "get_provider", lambda: FakeProvider())

    oid1 = upload(client, p, h).json()["order_id"]
    assert services.run_enrichment(oid1) == "done"
    assert calls["n"] == 1   # primeira vez consulta

    # segundo pedido com o mesmo username: perfil já "ok" e recente → reusa (não consulta)
    oid2 = upload(client, p, h).json()["order_id"]
    assert services.run_enrichment(oid2) == "done"
    assert calls["n"] == 1   # cache: provider não chamado de novo


@pytest.mark.parametrize("status", ["not_found", "private"])
def test_cache_nao_se_aplica_a_not_found_private(env, monkeypatch, status):
    """`not_found`/`private` são reconsultados na próxima tentativa, mesmo recentes."""
    from datetime import datetime, timezone

    from app import services
    from app.providers.base import ProfileResult
    from tests.helpers import make_zip, register, upload
    from tests.test_api import OLD

    client, Session, tmp = env
    h = register(client)
    p = tmp / "e.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[])

    calls = {"n": 0}
    class FakeProvider:
        name = "fake"
        def fetch(self, username):
            calls["n"] += 1
            return ProfileResult(status=status, source="fake", fetched_at=datetime.now(timezone.utc))
    monkeypatch.setattr(services, "get_provider", lambda: FakeProvider())

    oid1 = upload(client, p, h).json()["order_id"]
    assert services.run_enrichment(oid1) == "done"
    assert calls["n"] == 1

    oid2 = upload(client, p, h).json()["order_id"]
    assert services.run_enrichment(oid2) == "done"
    assert calls["n"] == 2   # reconsultado: sem cache para not_found/private
