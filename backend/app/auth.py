"""Autenticação: convite (backoffice) → aceite (define senha) → login.

Sem e-mail: o operador cria convites via `python -m app.invite` e distribui os
links fora da aplicação. Cada convite é de uso único e vale `INVITE_DAYS` dias
(em `services.py`). O e-mail é considerado válido no momento do convite.
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import rate, services
from .db import get_db
from .models import Invite, User
from .security import (DUMMY_HASH, REFRESH_DAYS, create_refresh_token, create_token,
                       decode_refresh_token, decode_token, hash_token,
                       password_fingerprint, verify_password)

COOKIE_NAME = "bkp_session"
REFRESH_COOKIE = "bkp_refresh"
COOKIE_PATH = "/"
PRODUCTION = os.getenv("APP_ENV", "development") == "production"

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

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=10, max_length=128)


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


# ---------- rotas ----------

@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not rate.hit(f"login:{_ip(request)}:{email}", 10, 900):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not (user and ok):
        raise HTTPException(401, "E-mail ou senha incorretos")

    fp = password_fingerprint(user.password_hash)
    access = create_token(user.id, fp, ver=user.token_version)
    refresh = create_refresh_token(user.id, ver=user.token_version)
    _set_session_cookie(response, access)
    _set_refresh_cookie(response, refresh)
    # também devolvemos no corpo para clientes que ainda usam Authorization
    return {"access_token": access, "token_type": "bearer"}


@router.post("/accept-invite", status_code=201)
def accept_invite(body: AcceptInviteIn, request: Request, response: Response,
                  db: Session = Depends(get_db)):
    if not rate.hit(f"accept:{_ip(request)}", 20, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    user = services.accept_invite(db, body.token, body.password)
    if user is None:
        raise HTTPException(400, "Convite inválido, expirado ou já utilizado.")
    # auto-login: define senha e já entra
    fp = password_fingerprint(user.password_hash)
    access = create_token(user.id, fp, ver=user.token_version)
    refresh = create_refresh_token(user.id, ver=user.token_version)
    _set_session_cookie(response, access)
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "token_type": "bearer"}


@router.get("/invite/{token}")
def invite_status(token: str, db: Session = Depends(get_db)):
    now_ = datetime.now(timezone.utc)
    inv = db.scalar(
        select(Invite).where(
            Invite.token_hash == hash_token(token),
            Invite.used_at.is_(None),
            Invite.expires_at > now_,
        )
    )
    if inv is None:
        raise HTTPException(404, "Convite inválido ou expirado.")
    return {"email": inv.email}


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
