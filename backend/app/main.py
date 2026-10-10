import os, uuid, zipfile
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .auth import router as auth_router, current_user
from .db import Base, engine, get_db
from .models import Order, Profile, User
from .services import create_order_from_zip, delete_orders, retention_days
from . import exporter

UPLOAD_DIR = "/data/uploads"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
KEEP_UPLOADS = os.getenv("KEEP_UPLOADS", "0") == "1"   # padrão: apagar o ZIP após processar

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)   # dev; Alembic mais tarde
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield

app = FastAPI(title="Backup enriquecido", lifespan=lifespan)
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"],
)

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
        except (zipfile.BadZipFile, ValueError, KeyError) as e:
            raise HTTPException(400, f"Arquivo inválido: {e}")
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
    from .worker import process_order
    order = _get_order(db, order_id, user)
    if order.status not in ("parsed", "failed"):
        raise HTTPException(409, f"Pedido em estado '{order.status}'")
    order.status = "queued"
    db.commit()
    process_order.delay(str(order.id))
    return {"order_id": str(order.id), "status": "queued"}

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
