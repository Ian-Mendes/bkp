from tests.helpers import PASSWORD, register

def test_registro_login_me(env):
    client, _, _ = env
    r = client.post("/auth/register", json={"email": "Ana@Empresa.com.br", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["email"] == "ana@empresa.com.br"
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=h).json()["email"] == "ana@empresa.com.br"

def test_email_duplicado_e_senha_curta(env):
    client, _, _ = env
    register(client)
    r = client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 409
    r = client.post("/auth/register", json={"email": "bia@empresa.com.br", "password": "curta"})
    assert r.status_code == 422

def test_login_errado_e_sem_token(env):
    client, _, _ = env
    register(client)
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"})
    assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "ninguem@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 401
    assert client.get("/orders").status_code == 401
    assert client.get("/orders", headers={"Authorization": "Bearer lixo"}).status_code == 401

def test_limite_de_tentativas_de_login(env):
    client, _, _ = env
    register(client)
    codes = [client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
