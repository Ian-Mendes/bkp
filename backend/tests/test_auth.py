from tests.helpers import PASSWORD, OUTBOX, register, register_unverified, last_token

def test_registro_login_me(env):
    client, _, _ = env
    r = client.post("/auth/register", json={"email": "Ana@Empresa.com.br", "password": PASSWORD})
    assert r.status_code == 201 and "access_token" not in r.json()
    assert client.post("/auth/verify-email", json={"token": last_token(), "password": PASSWORD}).status_code == 200
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=h).json()["email"] == "ana@empresa.com.br"

def test_email_duplicado_e_senha_curta(env):
    client, _, _ = env
    register(client)
    OUTBOX.clear()
    r = client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 201          # sem 409: não revela que o e-mail já tem conta
    assert len(OUTBOX) == 1 and OUTBOX[0][1] == "Tentativa de cadastro"
    r = client.post("/auth/register", json={"email": "bia@empresa.com.br", "password": "curta"})
    assert r.status_code == 422

def test_login_errado_e_sem_token(env):
    client, _, _ = env
    register(client)
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"})
    assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "ninguem@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 401
    client.cookies.clear()   # o register() deixou o cookie de sessão no cliente
    assert client.get("/orders").status_code == 401
    assert client.get("/orders", headers={"Authorization": "Bearer lixo"}).status_code == 401

def test_limite_de_tentativas_de_login(env):
    client, _, _ = env
    register_unverified(client)   # register() faria um login a mais e consumiria o limite
    codes = [client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "errada-errada"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429

def test_login_bloqueado_ate_confirmar_email(env):
    client, _, _ = env
    register_unverified(client)
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 403
    client.post("/auth/verify-email", json={"token": last_token(), "password": PASSWORD})
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 200

def test_verify_token_invalido_e_tipo_errado(env):
    client, _, _ = env
    assert client.post("/auth/verify-email", json={"token": "lixo", "password": PASSWORD}).status_code == 400
    # token de sessão não serve como token de verificação, nem o inverso
    h = register(client)
    session = h["Authorization"].split()[1]
    assert client.post("/auth/verify-email", json={"token": session, "password": PASSWORD}).status_code == 400
    verify = last_token()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {verify}"}).status_code == 401

def test_reenvio_de_confirmacao(env):
    client, _, _ = env
    register_unverified(client)
    OUTBOX.clear()
    r = client.post("/auth/resend-verification", json={"email": "ana@empresa.com.br"})
    assert r.status_code == 202 and len(OUTBOX) == 1
    # e-mail inexistente ou já confirmado: mesma resposta, nenhum envio
    client.post("/auth/verify-email", json={"token": last_token(), "password": PASSWORD})
    OUTBOX.clear()
    for e in ("ana@empresa.com.br", "ninguem@empresa.com.br"):
        assert client.post("/auth/resend-verification", json={"email": e}).status_code == 202
    assert OUTBOX == []

def test_recuperar_senha(env):
    client, _, _ = env
    register(client)
    OUTBOX.clear()
    r = client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"})
    assert r.status_code == 202 and len(OUTBOX) == 1
    token = last_token()
    nova = "outra-senha-bem-longa-456"
    assert client.post("/auth/reset-password", json={"token": token, "password": "curta"}).status_code == 422
    assert client.post("/auth/reset-password", json={"token": token, "password": nova}).status_code == 200
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": nova}).status_code == 200
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD}).status_code == 401
    # link de uso único
    assert client.post("/auth/reset-password", json={"token": token, "password": "mais-uma-senha-789"}).status_code == 400

def test_recuperar_senha_nao_revela_email(env):
    client, _, _ = env
    OUTBOX.clear()
    r1 = client.post("/auth/forgot-password", json={"email": "ninguem@empresa.com.br"})
    register(client)
    OUTBOX.clear()
    r2 = client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"})
    assert r1.status_code == r2.status_code == 202 and r1.json() == r2.json()

def test_reset_confirma_email_nao_verificado(env):
    client, _, _ = env
    register_unverified(client)
    client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"})
    nova = "outra-senha-bem-longa-456"
    assert client.post("/auth/reset-password", json={"token": last_token(), "password": nova}).status_code == 200
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": nova}).status_code == 200

def test_cadastro_resposta_igual_para_email_novo_e_existente(env):
    client, _, _ = env
    novo = client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    repetido = client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": "outra-senha-qualquer-1"})
    assert novo.status_code == repetido.status_code == 201
    assert novo.json() == repetido.json()
    # conta ainda pendente: vale a senha do cadastro mais recente
    client.post("/auth/verify-email", json={"token": last_token(), "password": "outra-senha-qualquer-1"})
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "outra-senha-qualquer-1"}).status_code == 200

def test_pre_sequestro_de_conta_pendente(env):
    client, _, _ = env
    # atacante cadastra o e-mail da vítima com a senha dele
    client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": "senha-do-atacante-1"})
    token_atacante = last_token()
    # a vítima se cadastra com a senha dela
    client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    token_vitima = last_token()
    # o link antigo (do atacante) morre; o novo vale
    assert client.post("/auth/verify-email", json={"token": token_atacante, "password": "senha-do-atacante-1"}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": token_vitima, "password": PASSWORD}).status_code == 200
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD}).status_code == 200
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": "senha-do-atacante-1"}).status_code == 401

def test_trocar_senha_derruba_sessoes_antigas(env):
    client, _, _ = env
    h = register(client)
    assert client.get("/auth/me", headers=h).status_code == 200
    client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"})
    nova = "outra-senha-bem-longa-456"
    client.post("/auth/reset-password", json={"token": last_token(), "password": nova})
    assert client.get("/auth/me", headers=h).status_code == 401          # sessão antiga caiu
    r = client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": nova})
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200

def test_teto_de_emails_por_destinatario_independe_do_ip(env, monkeypatch):
    from app import auth
    client, _, _ = env
    monkeypatch.setattr(auth, "EMAILS_PER_ADDRESS", 3)
    register_unverified(client)                         # o cadastro tem cota própria
    OUTBOX.clear()
    codes = []
    for i in range(4):
        # IP diferente a cada chamada não ajudaria: o teto é por endereço
        codes.append(client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"}).status_code)
    assert codes == [202, 202, 202, 429]
    assert len(OUTBOX) == 3
    # a resposta é a mesma para um e-mail que não existe
    for _ in range(3):
        client.post("/auth/forgot-password", json={"email": "ninguem@empresa.com.br"})
    assert client.post("/auth/forgot-password", json={"email": "ninguem@empresa.com.br"}).status_code == 429

def test_confirmar_email_exige_a_senha_do_cadastro(env):
    client, _, _ = env
    register_unverified(client)
    token = last_token()
    r = client.post("/auth/verify-email", json={"token": token, "password": "senha-errada-123"})
    assert r.status_code == 400
    assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": PASSWORD}).status_code == 403
    assert client.post("/auth/verify-email", json={"token": token, "password": PASSWORD}).status_code == 200

def test_pre_sequestro_atacante_por_ultimo_nao_ativa_a_conta(env):
    client, _, _ = env
    # vítima se cadastra; o atacante cadastra o mesmo e-mail depois, trocando a senha
    client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": "senha-do-atacante-1"})
    token = last_token()    # e-mail enviado à vítima (disparado pelo atacante)
    # a vítima clica e digita a senha que ELA escolheu: não confere, conta continua inativa
    assert client.post("/auth/verify-email", json={"token": token, "password": PASSWORD}).status_code == 400
    for senha in (PASSWORD, "senha-do-atacante-1"):
        assert client.post("/auth/login", json={"email": "ana@empresa.com.br", "password": senha}).status_code in (401, 403)

def test_esgotar_cadastro_nao_bloqueia_recuperacao_de_senha(env, monkeypatch):
    from app import auth
    client, _, _ = env
    monkeypatch.setattr(auth, "EMAILS_PER_ADDRESS", 2)
    register(client)                                       # 1 cadastro
    for _ in range(3):                                     # atacante insiste no cadastro do mesmo e-mail
        client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    r = client.post("/auth/register", json={"email": "ana@empresa.com.br", "password": PASSWORD})
    assert r.status_code == 429                            # cota de cadastro esgotada
    OUTBOX.clear()
    r = client.post("/auth/forgot-password", json={"email": "ana@empresa.com.br"})
    assert r.status_code == 202 and len(OUTBOX) == 1       # a recuperação continua funcionando
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
