"""Fila sem broker: `POST /start` enfileira e o poller processa (issue #14)."""
import uuid

from sqlalchemy import select

from app import poller, services
from app.models import Order
from tests.helpers import make_zip, register, upload, OLD


def _order(env, email="ana@empresa.com.br"):
    client, Session, tmp = env
    h = register(client, email)
    p = tmp / f"{email}.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[])
    return client, Session, h, upload(client, p, h).json()["order_id"]


def test_start_enfileira_sem_enriquecer(env):
    client, Session, h, oid = _order(env)
    r = client.post(f"/orders/{oid}/start", headers=h)
    assert r.status_code == 202
    assert r.json() == {"order_id": oid, "status": "queued"}
    with Session() as db:
        assert db.get(Order, uuid.UUID(oid)).status == "queued"
        assert {p.status for p in db.scalars(select(services.Profile))} == {"pending"}


def test_start_duplo_conflita(env):
    client, _, h, oid = _order(env)
    client.post(f"/orders/{oid}/start", headers=h)
    r = client.post(f"/orders/{oid}/start", headers=h)
    assert r.status_code == 409


def test_claim_pega_mais_antigo_e_marca_processing(env):
    client, Session, h, oid1 = _order(env)
    _, _, _, oid2 = _order(env, "bia@empresa.com.br")
    client.post(f"/orders/{oid1}/start", headers=h)
    with Session() as db:
        assert str(services.claim_queued_order(db)) == oid1
        assert db.get(Order, uuid.UUID(oid1)).status == "processing"
        assert services.claim_queued_order(db) is None   # oid2 segue parsed, fora da fila
    with Session() as db:
        assert db.get(Order, uuid.UUID(oid2)).status == "parsed"


def test_requeue_devolve_orfaos(env):
    _, Session, _, oid = _order(env)
    with Session() as db:
        db.get(Order, uuid.UUID(oid)).status = "processing"
        db.commit()
        assert services.requeue_orphans(db) == 1
        assert db.get(Order, uuid.UUID(oid)).status == "queued"
        assert services.requeue_orphans(db) == 0


def test_poller_processa_ate_done(env):
    client, Session, h, oid = _order(env)
    client.post(f"/orders/{oid}/start", headers=h)
    assert poller.run_once() == "done"
    assert poller.run_once() is None   # fila vazia
    with Session() as db:
        assert db.get(Order, uuid.UUID(oid)).status == "done"


def test_poller_marca_failed_sem_derrubar(env, monkeypatch):
    client, Session, h, oid = _order(env)
    client.post(f"/orders/{oid}/start", headers=h)
    monkeypatch.setattr(services, "run_enrichment", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert poller.run_once() == "failed"
    with Session() as db:
        assert db.get(Order, uuid.UUID(oid)).status == "failed"
