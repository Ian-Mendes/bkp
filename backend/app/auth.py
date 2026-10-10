from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import rate
from .db import get_db
from .models import User
from .security import (hash_password, verify_password, create_token,
                       decode_token, DUMMY_HASH)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

def current_user(creds=Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(401, "Não autenticado")
    uid = decode_token(creds.credentials)
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Token inválido ou expirado")
    return user

def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"

@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not rate.hit(f"reg:{_ip(request)}", 10, 3600):
        raise HTTPException(429, "Muitas tentativas. Tente mais tarde.")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return {"id": str(user.id), "email": user.email,
            "access_token": create_token(user.id), "token_type": "bearer"}

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
    return {"access_token": create_token(user.id), "token_type": "bearer"}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": str(user.id), "email": user.email}
