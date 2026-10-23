"""Testes da task Celery `process_order` e do enfileiramento em `start_order`."""
import pytest
from celery.exceptions import Retry

from app import worker
from tests.helpers import make_zip, register, upload, OLD, NEW


def _make_parsed_order(env):
    """Cria um pedido no estado `parsed` (pronto para `start`)."""
    client, Session, tmp = env
    h = register(client)
    p = tmp / "w.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[("carla", NEW)])
    r = upload(client, p, h)
    assert r.status_code == 200, r.text
    return client, Session, h, r.json()["order_id"]


def test_start_enfileira(env, fake_celery):
    """`start_order` muda status para `queued` e enfileira via `.delay()`."""
    client, Session, h, oid = _make_parsed_order(env)
    r = client.post(f"/orders/{oid}/start", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued"
    assert fake_celery == [oid]
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "queued"


def test_start_redis_indisponivel(env, monkeypatch):
    """Se `.delay()` falhar, o pedido volta para `parsed` e a API devolve 503."""
    client, Session, h, oid = _make_parsed_order(env)

    def boom(_):
        raise ConnectionError("redis down")

    monkeypatch.setattr(worker.process_order, "delay", boom)
    r = client.post(f"/orders/{oid}/start", headers=h)
    assert r.status_code == 503
    assert "Fila indisponível" in r.json()["detail"]
    # status restaurado → permite novo start
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "parsed"


def test_process_order_sucesso(env):
    """A task executa `run_enrichment` e devolve `done` (NullProvider)."""
    client, Session, h, oid = _make_parsed_order(env)
    assert worker.process_order.run(oid) == "done"
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "done"


def test_process_order_rate_limited_reagenda(env, monkeypatch):
    """Quando `run_enrichment` devolve `parsed`, a task chama `self.retry()`."""
    client, Session, h, oid = _make_parsed_order(env)
    monkeypatch.setattr(worker.services, "run_enrichment", lambda _oid: "parsed")
    with pytest.raises(Retry):
        worker.process_order.run(oid)
    # antes de reagendar, volta para `queued`
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "queued"


def test_process_order_excecao_reagenda(env, monkeypatch):
    """Exceções são capturadas e a task reagenda (re-levanta a original em `.run()`)."""
    client, Session, h, oid = _make_parsed_order(env)

    def boom(_oid):
        raise RuntimeError("provider explodiu")

    monkeypatch.setattr(worker.services, "run_enrichment", boom)
    with pytest.raises(RuntimeError, match="provider explodiu"):
        worker.process_order.run(oid)
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "queued"
