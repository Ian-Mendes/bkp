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
REFRESH_DAYS = int(os.getenv("REFRESH_DAYS", "30"))

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
DUMMY_HASH = _ph.hash("senha-ficticia-para-igualar-o-tempo-de-resposta")

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def create_token(user_id, fp: str | None = None, ver: int = 0) -> str:
    """Token de sessão. `fp` amarra à senha; `ver` permite revogação em massa."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {"sub": str(user_id), "exp": exp, "ver": ver}
    if fp:
        payload["fp"] = fp
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_token(token: str):
    """Devolve (user_id, fp, ver) de um token válido; senão None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if "purpose" in payload:
            return None
        return uuid.UUID(payload["sub"]), payload.get("fp"), payload.get("ver", 0)
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
REFRESH = "refresh"

def password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]

def create_purpose_token(user_id, purpose: str, minutes: int,
                         fp: str | None = None, ver: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": exp, "purpose": purpose, "ver": ver}
    if fp:
        payload["fp"] = fp
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_purpose_token(token: str, purpose: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("purpose") != purpose:
            return None
        return uuid.UUID(payload["sub"]), payload.get("fp"), payload.get("ver", 0)
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

def create_refresh_token(user_id, ver: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS)
    payload = {"sub": str(user_id), "exp": exp, "purpose": REFRESH, "ver": ver}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_refresh_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("purpose") != REFRESH:
            return None
        return uuid.UUID(payload["sub"]), payload.get("ver", 0)
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
