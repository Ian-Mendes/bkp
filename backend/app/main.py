import os, uuid, zipfile
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from .auth import router as auth_router, current_user
from .db import Base, engine, get_db
from .models import Order, Profile, User
from .importer import ExportError
from .services import (create_order_from_zip, delete_orders, retention_days,
                       run_enrichment, purge_expired_orders)
from . import exporter, rate

UPLOAD_DIR = "/data/uploads"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
KEEP_UPLOADS = os.getenv("KEEP_UPLOADS", "0") == "1"   # padrão: apagar o ZIP após processar
UPLOADS_PER_HOUR = int(os.getenv("UPLOADS_PER_HOUR", "10"))     # envios por usuário/hora
MAX_ORDERS_PER_USER = int(os.getenv("MAX_ORDERS_PER_USER", "20"))  # pedidos guardados por usuário
PRODUCTION = os.getenv("APP_ENV", "development") == "production"
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "0" if PRODUCTION else "1") == "1"

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)   # dev; Alembic mais tarde
    if engine.dialect.name == "postgresql":
        # create_all não altera tabelas existentes; contas anteriores à verificação ficam como confirmadas
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                              "email_verified BOOLEAN NOT NULL DEFAULT TRUE"))
            # contas novas nascem não confirmadas (mesmo default de um banco criado do zero)
            conn.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE"))
            # NOVO: token_version para revogação em massa (logout/troca de senha)
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                              "token_version INTEGER NOT NULL DEFAULT 0"))
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    scheduler = BackgroundScheduler()
    # single-instance: cada worker do uvicorn rodaria o próprio agendador (purga é idempotente)
    scheduler.add_job(purge_expired_orders, "interval", hours=24)
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)

app = FastAPI(
    title="Backup enriquecido", lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)
app.include_router(auth_router)

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
MAX_BODY_OTHER = 64 * 1024          # JSON de login, cadastro etc.

def _too_large(request: Request) -> bool:
    """Rejeita pelo Content-Length antes do FastAPI gravar o corpo em disco.
    Corpos chunked não trazem o cabeçalho: o limite definitivo deve ficar também no proxy."""
    if request.method not in ("POST", "PUT", "PATCH"):
        return False
    try:
        size = int(request.headers.get("content-length", "0"))
    except ValueError:
        return True
    limit = (MAX_UPLOAD_MB + 1) * 1024 * 1024 if request.url.path == "/orders" else MAX_BODY_OTHER
    return size > limit

@app.middleware("http")
async def security_headers(request: Request, call_next):
    if _too_large(request):
        response = JSONResponse({"detail": "Requisição grande demais"}, status_code=413)
    else:
        response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    h["Cross-Origin-Resource-Policy"] = "same-site"
    if request.url.path.startswith("/auth") or request.url.path.startswith("/orders"):
        h["Cache-Control"] = "no-store"
    if not request.url.path.startswith(_DOC_PATHS):   # o Swagger carrega scripts de CDN
        h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if PRODUCTION:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

def _get_order(db, order_id, user):
    order = db.get(Order, order_id)
    if not order or order.user_id != user.id:     # 404 também para pedido alheio
        raise HTTPException(404, "Pedido não encontrado")
    return order

@app.post("/orders")
def create_order(file: UploadFile = File(...),
                 expected_followers: int | None = Form(None, ge=1),
                 expected_following: int | None = Form(None, ge=1),
                 user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    if not rate.hit(f"upload:{user.id}", UPLOADS_PER_HOUR, 3600):
        raise HTTPException(429, "Muitos envios. Tente novamente mais tarde.")
    # trava a linha do usuário: dois envios simultâneos não passam juntos pela cota (no-op em SQLite)
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    stored = db.scalar(select(func.count()).select_from(Order).where(Order.user_id == user.id))
    if stored >= MAX_ORDERS_PER_USER:
        raise HTTPException(409, "Limite de pedidos atingido. Exclua algum pedido antes de enviar outro.")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.zip")
    try:
        size = 0
        with open(path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Arquivo acima de {MAX_UPLOAD_MB} MB. Exporte só 'Seguidores e seguindo'.")
                out.write(chunk)
        try:
            order = create_order_from_zip(db, path, file.filename, user.id,
                                          expected_followers, expected_following)
        except ExportError as e:
            raise HTTPException(400, str(e))
        except (zipfile.BadZipFile, ValueError, KeyError):
            raise HTTPException(400, "Arquivo inválido. Envie o ZIP de 'Seguidores e seguindo' exportado pelo Instagram.")
    finally:
        if not KEEP_UPLOADS and os.path.exists(path):
            os.remove(path)
    info = order.info or {}
    return {"order_id": str(order.id), "status": order.status,
            "followers": order.followers_total, "following": order.following_total,
            "invalid": order.invalid_count, "duplicates": order.duplicate_count,
            "ranges": info.get("ranges"), "coverage": info.get("coverage"),
            "warnings": info.get("warnings", [])}

@app.get("/orders")
def list_orders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).where(Order.user_id == user.id)
                      .order_by(Order.created_at.desc())).all()
    days = retention_days()
    return [{"order_id": str(o.id), "status": o.status,
             "followers": o.followers_total, "following": o.following_total,
             "created_at": o.created_at.isoformat(),
             "expires_at": (o.created_at + timedelta(days=days)).isoformat()} for o in rows]

@app.get("/orders/{order_id}")
def get_order(order_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = _get_order(db, order_id, user)
    rows = db.execute(select(Profile.status, func.count()).where(Profile.order_id == order_id)
                      .group_by(Profile.status)).all()
    return {"order_id": str(order.id), "status": order.status,
            "followers": order.followers_total, "following": order.following_total,
            "profiles_by_status": {s: n for s, n in rows}}

@app.post("/orders/{order_id}/start")
def start_order(order_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = _get_order(db, order_id, user)
    if order.status not in ("parsed", "failed"):
        raise HTTPException(409, f"Pedido em estado '{order.status}'")
    status = run_enrichment(str(order.id))
    return {"order_id": str(order.id), "status": status}

@app.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = _get_order(db, order_id, user)
    if order.status in ("queued", "processing"):
        raise HTTPException(409, "Pedido em processamento; tente após a conclusão")
    delete_orders(db, [order.id])
    return Response(status_code=204)

@app.get("/orders/{order_id}/report")
def report(order_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return exporter.build_report(db, _get_order(db, order_id, user))

@app.get("/orders/{order_id}/export.csv")
def export_csv(order_id: uuid.UUID,
               sort_by: Literal["followers_count", "following_count", "username"] = "followers_count",
               direction: Literal["asc", "desc"] = "desc",
               q: str | None = None,
               user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    _get_order(db, order_id, user)
    profiles = db.scalars(exporter.query_profiles(order_id, sort_by, direction, q)).all()
    return Response(exporter.to_csv(profiles), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="backup_enriquecido.csv"'})

@app.get("/orders/{order_id}/export.xlsx")
def export_xlsx(order_id: uuid.UUID,
                sort_by: Literal["followers_count", "following_count", "username"] = "followers_count",
                direction: Literal["asc", "desc"] = "desc",
                q: str | None = None,
                user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    order = _get_order(db, order_id, user)
    profiles = db.scalars(exporter.query_profiles(order_id, sort_by, direction, q)).all()
    data = exporter.to_xlsx(profiles, exporter.build_report(db, order))
    return Response(data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="backup_enriquecido.xlsx"'})
