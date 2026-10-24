from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import services
from app.models import Invite
from app.security import hash_token
from tests.helpers import PASSWORD, invite, register


def test_convite_aceito_autentica_e_login(env):
    client, _, _ = env
    token = invite(client, "Ana@Empresa.com.br")
    r = client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD})
    assert r.status_code == 201
    assert "access_token" in r.json()
    # auto-login: o cookie de sessão já autentica
    assert client.get("/auth/me").json()["email"] == "ana@empresa.com.br"
    # e o login normal também funciona
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 200
    assert client.get("/auth/me").json()["email"] == "ana@empresa.com.br"


def test_status_do_convite(env):
    client, _, _ = env
    token = invite(client, "ana@empresa.com.br")
    r = client.get(f"/auth/invite/{token}")
    assert r.status_code == 200 and r.json()["email"] == "ana@empresa.com.br"
    assert client.get("/auth/invite/lixo").status_code == 404


def test_aceitar_convite_invalido(env):
    client, _, _ = env
    assert client.post("/auth/accept-invite", json={"token": "lixo", "password": PASSWORD}).status_code == 400


def test_aceitar_convite_senha_curta(env):
    client, _, _ = env
    token = invite(client, "ana@empresa.com.br")
    assert client.post("/auth/accept-invite", json={"token": token, "password": "curta"}).status_code == 422


def test_convite_uso_unico(env):
    client, _, _ = env
    token = invite(client, "ana@empresa.com.br")
    assert client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD}).status_code == 201
    assert client.post("/auth/accept-invite", json={"token": token, "password": "outra-senha-bem-longa-1"}).status_code == 400


def test_convite_expirado(env):
    client, Session, _ = env
    token = invite(client, "ana@empresa.com.br")
    with Session() as db:
        inv = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
        inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    assert client.get(f"/auth/invite/{token}").status_code == 404
    assert client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD}).status_code == 400


def test_reconvite_invalida_link_antigo(env):
    client, _, _ = env
    t1 = invite(client, "ana@empresa.com.br")
    t2 = invite(client, "ana@empresa.com.br")
    assert t1 != t2
    assert client.get(f"/auth/invite/{t1}").status_code == 404
    assert client.post("/auth/accept-invite", json={"token": t2, "password": PASSWORD}).status_code == 201


def test_convite_ignora_email_ja_cadastrado(env):
    client, _, _ = env
    register(client, "ana@empresa.com.br")
    with services.SessionLocal() as db:
        assert services.create_invite(db, "ana@empresa.com.br") is None


def test_login_senha_errada_e_rate_limit(env):
    client, _, _ = env
    register(client, "ana@empresa.com.br")
    client.cookies.clear()
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"}).status_code == 401
    codes = [client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"}).status_code
             for _ in range(10)]
    assert codes[-1] == 429


def test_cookie_de_sessao_autentica_e_logout_limpa(env):
    client, _, _ = env
    headers = register(client)
    access = client.cookies.get("bkp_session")
    refresh = client.cookies.get("bkp_refresh")
    assert client.get("/orders").status_code == 200   # cookie guardado pelo login
    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert response.content == b""
    assert len(response.headers.get_list("set-cookie")) == 2
    assert response.headers["cache-control"] == "no-store"
    assert client.cookies.get("bkp_session") is None
    assert client.cookies.get("bkp_refresh") is None
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 401
    client.cookies.set("bkp_session", access)
    client.cookies.set("bkp_refresh", refresh)
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/refresh").status_code == 401
    assert client.post("/auth/logout").status_code == 204


def test_logout_com_apenas_refresh_revoga_sessao(env):
    client, _, _ = env
    headers = register(client)
    refresh = client.cookies.get("bkp_refresh")
    client.cookies.clear()
    client.cookies.set("bkp_refresh", refresh)
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    client.cookies.set("bkp_refresh", refresh)
    assert client.post("/auth/refresh").status_code == 401


def test_logout_sem_sessao_limpa_cookies(env):
    client, _, _ = env
    client.cookies.set("bkp_session", "invalido", domain="testserver.local", path="/")
    client.cookies.set("bkp_refresh", "invalido", domain="testserver.local", path="/")
    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert client.cookies.get("bkp_session") is None
    assert client.cookies.get("bkp_refresh") is None
