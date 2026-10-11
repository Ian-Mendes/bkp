import smtplib
from starlette.requests import Request
from app import mailer, worker, main
from tests.conftest import REAL_ENQUEUE

# ---------- enqueue_email ----------

def test_enqueue_envia_para_a_fila(monkeypatch):
    chamadas = []
    monkeypatch.setattr(worker.send_email, "apply_async",
                        lambda **kw: chamadas.append(kw))
    REAL_ENQUEUE("ana@empresa.com.br", "Assunto", "Corpo")
    assert chamadas[0]["args"] == ("ana@empresa.com.br", "Assunto", "Corpo")
    assert chamadas[0]["retry_policy"]["max_retries"] == 1      # falha rápida se o Redis cair

def test_enqueue_com_fila_fora_do_ar_nao_derruba_a_requisicao(monkeypatch):
    def boom(**kw):
        raise ConnectionError("redis fora")
    monkeypatch.setattr(worker.send_email, "apply_async", boom)
    REAL_ENQUEUE("ana@empresa.com.br", "Assunto", "Corpo")      # não deve levantar exceção

# ---------- tarefa send_email ----------

def test_tarefa_send_email_chama_o_smtp(monkeypatch):
    enviados = []
    monkeypatch.setattr(mailer, "send_smtp", lambda to, s, t: enviados.append((to, s, t)))
    worker.send_email.run("ana@empresa.com.br", "Assunto", "Corpo")
    assert enviados == [("ana@empresa.com.br", "Assunto", "Corpo")]

def test_tarefa_repete_em_erro_de_rede():
    # smtplib.SMTPException herda de OSError, que é o que autoretry_for cobre
    assert issubclass(smtplib.SMTPException, OSError)
    assert OSError in worker.send_email.autoretry_for

# ---------- mailer ----------

class FakeSMTP:
    instances = []
    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.calls, self.msg = host, port, [], None
        FakeSMTP.instances.append(self)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): self.calls.append("starttls")
    def login(self, user, pw): self.calls.append(("login", user, pw))
    def send_message(self, msg): self.msg = msg

def test_mailer_envia_mensagem_simples(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS", "MAIL_FROM"):
        monkeypatch.delenv(k, raising=False)
    mailer.send_smtp("ana@empresa.com.br", "Olá", "Texto")
    s = FakeSMTP.instances[0]
    assert (s.host, s.port) == ("mailpit", 1025)            # padrão de desenvolvimento
    assert s.calls == []                                     # sem TLS nem login no Mailpit
    assert s.msg["To"] == "ana@empresa.com.br" and s.msg["Subject"] == "Olá"
    assert s.msg.get_content().strip() == "Texto"

def test_mailer_usa_tls_e_login_quando_configurado(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.exemplo.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "usuario")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    monkeypatch.setenv("SMTP_STARTTLS", "1")
    mailer.send_smtp("ana@empresa.com.br", "Assunto", "Texto")
    s = FakeSMTP.instances[0]
    assert (s.host, s.port) == ("smtp.exemplo.com", 587)
    assert s.calls == ["starttls", ("login", "usuario", "segredo")]   # TLS antes do login

def test_frontend_url_sem_barra_final(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.exemplo.com/")
    assert mailer.frontend_url() == "https://app.exemplo.com"

# ---------- limite de corpo ----------

def _req(method, path, content_length):
    headers = [] if content_length is None else [(b"content-length", content_length)]
    return Request({"type": "http", "method": method, "path": path, "headers": headers})

def test_content_length_malformado_e_rejeitado():
    assert main._too_large(_req("POST", "/auth/login", b"abc")) is True

def test_content_length_ausente_ou_em_get_passa():
    assert main._too_large(_req("POST", "/auth/login", None)) is False
    assert main._too_large(_req("GET", "/orders", b"999999999999")) is False

def test_limite_de_corpo_por_rota():
    assert main._too_large(_req("POST", "/auth/login", str(70 * 1024).encode())) is True
    assert main._too_large(_req("POST", "/auth/login", b"1000")) is False
    dentro = str(main.MAX_UPLOAD_MB * 1024 * 1024).encode()
    acima = str((main.MAX_UPLOAD_MB + 2) * 1024 * 1024).encode()
    assert main._too_large(_req("POST", "/orders", dentro)) is False
    assert main._too_large(_req("POST", "/orders", acima)) is True
