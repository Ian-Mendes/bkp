import os, uuid, hashlib
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

JWT_SECRET = os.environ["JWT_SECRET"]
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET precisa ter pelo menos 32 caracteres")
ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "60"))

_ph = PasswordHasher()
DUMMY_HASH = _ph.hash("senha-ficticia-para-igualar-o-tempo-de-resposta")

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def create_token(user_id, fp: str | None = None) -> str:
    """Token de sessão. `fp` amarra a sessão à senha atual: trocar a senha derruba as sessões."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {"sub": str(user_id), "exp": exp}
    if fp:
        payload["fp"] = fp
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_token(token: str):
    """Devolve (user_id, fp) de um token de sessão válido; senão None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if "purpose" in payload:      # tokens de e-mail não valem como sessão
            return None
        return uuid.UUID(payload["sub"]), payload.get("fp")
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"

def password_fingerprint(password_hash: str) -> str:
    """Muda quando a senha muda: invalida o link de redefinição já usado."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]

def create_purpose_token(user_id, purpose: str, minutes: int, fp: str | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": exp, "purpose": purpose}
    if fp:
        payload["fp"] = fp
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_purpose_token(token: str, purpose: str):
    """Devolve (user_id, fp) se o token for válido para o propósito; senão None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("purpose") != purpose:
            return None
        return uuid.UUID(payload["sub"]), payload.get("fp")
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
