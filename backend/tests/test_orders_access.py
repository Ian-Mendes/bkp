import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app import worker
from app.models import Order, Profile
from tests.helpers import make_zip, register, upload, OLD, NEW

def _make_order(env, email):
    client, Session, tmp = env
    h = register(client, email)
    p = tmp / f"{email}.zip"
    make_zip(p, followers=[("ana_silva", OLD)], following=[("carla", NEW)])
    return h, upload(client, p, h).json()["order_id"]

def test_isolamento_entre_clientes(env):
    client, Session, tmp = env
    ha, oid = _make_order(env, "ana@empresa.com.br")
    hb = register(client, "bia@empresa.com.br")
    for method, url in [("get", f"/orders/{oid}"), ("get", f"/orders/{oid}/report"),
                        ("get", f"/orders/{oid}/export.csv"), ("get", f"/orders/{oid}/export.xlsx"),
                        ("post", f"/orders/{oid}/start"), ("delete", f"/orders/{oid}")]:
        assert getattr(client, method)(url, headers=hb).status_code == 404, url
    assert client.get("/orders", headers=hb).json() == []
    assert len(client.get("/orders", headers=ha).json()) == 1
    assert client.get(f"/orders/{oid}", headers=ha).status_code == 200

def test_excluir_pedido(env):
    client, Session, tmp = env
    h, oid = _make_order(env, "ana@empresa.com.br")
    assert client.delete(f"/orders/{oid}", headers=h).status_code == 204
    assert client.get(f"/orders/{oid}", headers=h).status_code == 404
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Profile)) == 0

def test_nao_exclui_em_processamento(env):
    client, Session, tmp = env
    h, oid = _make_order(env, "ana@empresa.com.br")
    with Session() as db:
        db.get(Order, uuid.UUID(oid)).status = "processing"
        db.commit()
    assert client.delete(f"/orders/{oid}", headers=h).status_code == 409

def test_retencao_apaga_pedidos_antigos(env):
    client, Session, tmp = env
    h, oid = _make_order(env, "ana@empresa.com.br")
    h2, oid2 = _make_order(env, "bia@empresa.com.br")
    with Session() as db:
        db.get(Order, uuid.UUID(oid)).created_at = datetime.now(timezone.utc) - timedelta(days=400)
        db.commit()
    assert worker.purge_expired.apply().get() == 1
    assert client.get(f"/orders/{oid}", headers=h).status_code == 404
    assert client.get(f"/orders/{oid2}", headers=h2).status_code == 200
