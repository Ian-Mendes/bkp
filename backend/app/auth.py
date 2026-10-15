"""Autenticação: cadastro, login, confirmação de e-mail e recuperação de senha.

E-mails são enviados com `BackgroundTasks` do FastAPI (rodam depois da resposta,
no mesmo processo). Suficiente para o volume baixo do MVP; não há retry nem
persistência. Se um provedor SMTP real exigir confiabilidade, mova o envio para
uma fila (Celery/Redis) — o ponto único de troca é `enqueue_email`.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from . import rate, mailer
from .db import get_db
from .models import User
from .security import (hash_password, verify_password, create_token,
                       decode_token, DUMMY_HASH, VERIFY_EMAIL, RESET_PASSWORD,
                       create_purpose_token, decode_purpose_token,
                       password_fingerprint, REFRESH_DAYS,
                       create_refresh_token, decode_refresh_token)

EMAILS_PER_ADDRESS = 6          # e-mails por endereço de destino/hora, em cada fluxo

VERIFY_MINUTES = 24 * 60
RESET_MINUTES = 30

COOKIE_NAME = "bkp_session"
REFRESH_COOKIE = "bkp_refresh"
COOKIE_PATH = "/"
PRODUCTION = __import__("os").getenv("APP_ENV", "development") == "production"

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


# ---------- cookie helpers ----------

def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME, value=token,
        max_age=60 * 60,  # 1h, igual ao TOKEN_MINUTES padrão
        httponly=True, secure=PRODUCTION, samesite="lax", path=COOKIE_PATH,
    )

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE, value=token,
        max_age=REFRESH_DAYS * 24 * 60 * 60,
        httponly=True, secure=PRODUCTION, samesite="lax", path=COOKIE_PATH,
    )

def _clear_cookies(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


# ---------- schemas ----------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class EmailIn(BaseModel):
    email: EmailStr

class VerifyIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=1, max_length=128)

class ResetIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=10, max_length=128)

def enqueue_email(background_tasks: BackgroundTasks, to: str, subject: str, text: str) -> None:
    """Agenda o envio para depois da resposta; o SMTP não bloqueia a requisição."""
    background_tasks.add_task(mailer.send_smtp, to, subject, text)

# ---------- email helpers ----------

NL = chr(10)

def _body(*parts: str) -> str:
    return (NL * 2).join(parts)

def _send_verification(user: User, background_tasks: BackgroundTasks) -> None:
    token = create_purpose_token(user.id, VERIFY_EMAIL, VERIFY_MINUTES,
                                 fp=password_fingerprint(user.password_hash),
                                 ver=user.token_version)
    link = f"{mailer.frontend_url()}/verify-email?token={token}"
    enqueue_email(background_tasks, user.email, "Confirme seu e-mail", _body(
        "Olá!",
        "Confirme seu e-mail para ativar sua conta (o link vale por 24 horas):" + NL + link,
        "Se você não criou esta conta, ignore esta mensagem."))

def _send_reset(user: User, background_tasks: BackgroundTasks) -> None:
    token = create_purpose_token(user.id, RESET_PASSWORD, RESET_MINUTES,
                                 fp=password_fingerprint(user.password_hash),
                                 ver=user.token_version)
    link = f"{mailer.frontend_url()}/reset-password?token={token}"
    enqueue_email(background_tasks, user.email, "Redefinição de senha", _body(
        "Olá!",
        "Para definir uma nova senha (o link vale por 30 minutos e só pode ser usado uma vez):" + NL + link,
        "Se você não pediu isso, ignore esta mensagem; sua senha continua a mesma."))


# ---------- dependencies ----------

def current_user(request: Request, creds=Depends(bearer), db: Session = Depends(get_db)) -> User:
    """Lê Authorization (compat) OU cookie httpOnly."""
    token = creds.credentials if creds else request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Não autenticado")
    decoded = decode_token(token)
    user = db.get(User, decoded[0]) if decoded else None
    # confere fingerprint da senha E versão (revogação em massa)
    if (user is None
            or decoded[1] != password_fingerprint(user.password_hash)
            or decoded[2] != user.token_version):
        raise HTTPException(401, "Token inválido ou expirado")
    return user


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"

def _email_budget(email: str, flow: str) -> None:
    if not rate.hit(f"mail:{flow}:{email}", EMAILS_PER_ADDRESS, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")


REGISTERED = {"message": "Se o cadastro for possível, enviamos um e-mail com as instruções."}
GENERIC = {"message": "Se o e-mail estiver cadastrado, enviaremos as instruções."}


def _send_already_registered(user: User, background_tasks: BackgroundTasks) -> None:
    enqueue_email(background_tasks, user.email, "Tentativa de cadastro", _body(
        "Olá!",
        "Alguém tentou criar uma conta com este e-mail, mas ele já está cadastrado. "
        "Se foi você, entre normalmente ou use \"Esqueci minha senha\" em " + mailer.frontend_url() + "/login",
        "Se não foi você, ignore esta mensagem; nada foi alterado."))


# ---------- rotas ----------

@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db)):
    if not rate.hit(f"reg:{_ip(request)}", 10, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    email = body.email.lower()
    _email_budget(email, "register")
    password_hash = hash_password(body.password)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is None:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.commit()
        _send_verification(user, background_tasks)
    elif existing.email_verified:
        _send_already_registered(existing, background_tasks)
    else:
        # novo cadastro de conta pendente: nova senha + incrementa versão (invalida links antigos)
        existing.password_hash = password_hash
        existing.token_version += 1
        db.commit()
        _send_verification(existing, background_tasks)
    return REGISTERED


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"login:{_ip(request)}:{email}", 10, 900):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not (user and ok):
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not user.email_verified:
        raise HTTPException(403, "E-mail ainda não confirmado. Verifique sua caixa de entrada.")

    fp = password_fingerprint(user.password_hash)
    access = create_token(user.id, fp, ver=user.token_version)
    refresh = create_refresh_token(user.id, ver=user.token_version)
    _set_session_cookie(response, access)
    _set_refresh_cookie(response, refresh)
    # também devolvemos no corpo para clientes que ainda usam Authorization
    return {"access_token": access, "token_type": "bearer"}


@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(401, "Sem refresh token")
    decoded = decode_refresh_token(token)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None or decoded[1] != user.token_version:
        raise HTTPException(401, "Refresh inválido")
    fp = password_fingerprint(user.password_hash)
    access = create_token(user.id, fp, ver=user.token_version)
    _set_session_cookie(response, access)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, creds=Depends(bearer),
           db: Session = Depends(get_db)):
    token = creds.credentials if creds else request.cookies.get(COOKIE_NAME)
    access = decode_token(token) if token else None
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    refresh = decode_refresh_token(refresh_token) if refresh_token else None
    # O refresh permite revogar a sessão mesmo quando o access já expirou.
    identity = (access[0], access[2]) if access else refresh
    if identity:
        db.execute(update(User).where(User.id == identity[0],
                                      User.token_version == identity[1])
                   .values(token_version=User.token_version + 1))
        db.commit()
    _clear_cookies(response)
    response.status_code = 204
    return response


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": str(user.id), "email": user.email}


@router.post("/verify-email")
def verify_email(body: VerifyIn, request: Request, db: Session = Depends(get_db)):
    decoded = decode_purpose_token(body.token, VERIFY_EMAIL)
    # rate limit por usuário quando o token for válido; senão, por IP
    key = f"verify:user:{decoded[0]}" if decoded else f"verify:ip:{_ip(request)}"
    if not rate.hit(key, 20, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    user = db.get(User, decoded[0]) if decoded else None
    if (user is None
            or decoded[1] != password_fingerprint(user.password_hash)
            or decoded[2] != user.token_version):
        raise HTTPException(400, "Link inválido ou expirado")
    if user.email_verified:
        return {"message": "E-mail confirmado. Você já pode entrar."}
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(400, "Senha incorreta. Use a senha que você definiu no cadastro.")
    user.email_verified = True
    db.commit()
    return {"message": "E-mail confirmado. Você já pode entrar."}


@router.post("/resend-verification", status_code=202)
def resend_verification(body: EmailIn, request: Request, background_tasks: BackgroundTasks,
                        db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"resend:{_ip(request)}:{email}", 5, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    _email_budget(email, "verify")
    user = db.scalar(select(User).where(User.email == email))
    if user and not user.email_verified:
        _send_verification(user, background_tasks)
    return GENERIC


@router.post("/forgot-password", status_code=202)
def forgot_password(body: EmailIn, request: Request, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"forgot:{_ip(request)}:{email}", 5, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    _email_budget(email, "forgot")
    user = db.scalar(select(User).where(User.email == email))
    if user:
        _send_reset(user, background_tasks)
    return GENERIC


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    if not rate.hit(f"reset:{_ip(request)}", 20, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    decoded = decode_purpose_token(body.token, RESET_PASSWORD)
    user = db.get(User, decoded[0]) if decoded else None
    if (user is None
            or decoded[1] != password_fingerprint(user.password_hash)
            or decoded[2] != user.token_version):
        raise HTTPException(400, "Link inválido ou expirado")
    user.password_hash = hash_password(body.password)
    user.email_verified = True
    user.token_version += 1   # derruba todas as sessões (access e refresh)
    db.commit()
    return {"message": "Senha alterada. Você já pode entrar."}
