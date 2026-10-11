import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import rate, mailer
from .db import get_db
from .models import User
from .security import (hash_password, verify_password, create_token,
                       decode_token, DUMMY_HASH, VERIFY_EMAIL, RESET_PASSWORD,
                       create_purpose_token, decode_purpose_token,
                       password_fingerprint)

log = logging.getLogger(__name__)
EMAILS_PER_ADDRESS = 6          # e-mails por endereço de destino/hora, em cada fluxo
VERIFY_MINUTES = 24 * 60
RESET_MINUTES = 30

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)

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

def enqueue_email(to: str, subject: str, text: str) -> None:
    """Envia em segundo plano (Celery). Falha de fila não derruba a requisição."""
    try:
        from .worker import send_email
        # falha rápida se o Redis estiver fora (não deixa o cadastro pendurado)
        send_email.apply_async(args=(to, subject, text), retry=True,
                               retry_policy={"max_retries": 1, "interval_start": 0.1, "interval_max": 0.3})
    except Exception:
        log.exception("Falha ao enfileirar e-mail para %s", to)

NL = chr(10)

def _body(*parts: str) -> str:
    return (NL * 2).join(parts)

def _send_verification(user: User) -> None:
    token = create_purpose_token(user.id, VERIFY_EMAIL, VERIFY_MINUTES,
                                 fp=password_fingerprint(user.password_hash))
    link = f"{mailer.frontend_url()}/verify-email?token={token}"
    enqueue_email(user.email, "Confirme seu e-mail", _body(
        "Olá!",
        "Confirme seu e-mail para ativar sua conta (o link vale por 24 horas):" + NL + link,
        "Se você não criou esta conta, ignore esta mensagem."))

def _send_reset(user: User) -> None:
    token = create_purpose_token(user.id, RESET_PASSWORD, RESET_MINUTES,
                                 fp=password_fingerprint(user.password_hash))
    link = f"{mailer.frontend_url()}/reset-password?token={token}"
    enqueue_email(user.email, "Redefinição de senha", _body(
        "Olá!",
        "Para definir uma nova senha (o link vale por 30 minutos e só pode ser usado uma vez):" + NL + link,
        "Se você não pediu isso, ignore esta mensagem; sua senha continua a mesma."))


def current_user(creds=Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(401, "Não autenticado")
    decoded = decode_token(creds.credentials)
    user = db.get(User, decoded[0]) if decoded else None
    # sessão amarrada à senha: após trocar a senha, tokens antigos deixam de valer
    if user is None or decoded[1] != password_fingerprint(user.password_hash):
        raise HTTPException(401, "Token inválido ou expirado")
    return user

def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"

def _email_budget(email: str, flow: str) -> None:
    """Teto de e-mails por destinatário, independente do IP (evita encher a caixa de terceiros).
    Aplicado antes de consultar o banco, então a resposta não revela se a conta existe.
    A cota é por fluxo: esgotar o cadastro ou o reenvio não bloqueia a recuperação de senha."""
    if not rate.hit(f"mail:{flow}:{email}", EMAILS_PER_ADDRESS, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")

REGISTERED = {"message": "Se o cadastro for possível, enviamos um e-mail com as instruções."}

def _send_already_registered(user: User) -> None:
    enqueue_email(user.email, "Tentativa de cadastro", _body(
        "Olá!",
        "Alguém tentou criar uma conta com este e-mail, mas ele já está cadastrado. "
        "Se foi você, entre normalmente ou use \"Esqueci minha senha\" em " + mailer.frontend_url() + "/login",
        "Se não foi você, ignore esta mensagem; nada foi alterado."))

@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not rate.hit(f"reg:{_ip(request)}", 10, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    email = body.email.lower()
    _email_budget(email, "register")
    # resposta idêntica para e-mail novo ou já cadastrado (não revela quem tem conta);
    # o hash é calculado nos dois casos para igualar o tempo de resposta
    password_hash = hash_password(body.password)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is None:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.commit()
        _send_verification(user)
    elif existing.email_verified:
        _send_already_registered(existing)
    else:
        # conta pendente: vale a senha do cadastro mais recente e os links anteriores são invalidados.
        # Evita que quem cadastrou o e-mail de outra pessoa primeiro fique com a senha da conta.
        existing.password_hash = password_hash
        db.commit()
        _send_verification(existing)
    return REGISTERED

@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"login:{_ip(request)}:{email}", 10, 900):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    user = db.scalar(select(User).where(User.email == email))
    # verifica sempre um hash, para o tempo de resposta não revelar se o e-mail existe
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not (user and ok):
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not user.email_verified:
        raise HTTPException(403, "E-mail ainda não confirmado. Verifique sua caixa de entrada.")
    return {"access_token": create_token(user.id, password_fingerprint(user.password_hash)),
            "token_type": "bearer"}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": str(user.id), "email": user.email}

GENERIC = {"message": "Se o e-mail estiver cadastrado, enviaremos as instruções."}

@router.post("/verify-email")
def verify_email(body: VerifyIn, request: Request, db: Session = Depends(get_db)):
    if not rate.hit(f"verify:{_ip(request)}", 20, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    decoded = decode_purpose_token(body.token, VERIFY_EMAIL)
    user = db.get(User, decoded[0]) if decoded else None
    # o link vale para a senha vigente quando foi enviado: novo cadastro com outra senha invalida o anterior
    if user is None or decoded[1] != password_fingerprint(user.password_hash):
        raise HTTPException(400, "Link inválido ou expirado")
    if not user.email_verified:
        # exige a senha: quem não a escolheu (ex.: cadastrou o e-mail alheio antes) não consegue ativar a conta
        if not verify_password(user.password_hash, body.password):
            raise HTTPException(400, "Senha incorreta. Use a senha que você definiu no cadastro.")
        user.email_verified = True
        db.commit()
    return {"message": "E-mail confirmado. Você já pode entrar."}

@router.post("/resend-verification", status_code=202)
def resend_verification(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"resend:{_ip(request)}:{email}", 5, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    _email_budget(email, "verify")
    user = db.scalar(select(User).where(User.email == email))
    if user and not user.email_verified:
        _send_verification(user)
    return GENERIC

@router.post("/forgot-password", status_code=202)
def forgot_password(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"forgot:{_ip(request)}:{email}", 5, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    _email_budget(email, "forgot")
    user = db.scalar(select(User).where(User.email == email))
    if user:
        _send_reset(user)
    return GENERIC

@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    if not rate.hit(f"reset:{_ip(request)}", 20, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    decoded = decode_purpose_token(body.token, RESET_PASSWORD)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None or decoded[1] != password_fingerprint(user.password_hash):
        raise HTTPException(400, "Link inválido ou expirado")
    user.password_hash = hash_password(body.password)
    user.email_verified = True      # quem recebeu o link controla o e-mail
    db.commit()
    return {"message": "Senha alterada. Você já pode entrar."}
