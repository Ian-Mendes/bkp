import os, uuid
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import select
from . import mailer
from .db import SessionLocal
from .models import Order, Profile
from .providers import get_provider
from .services import delete_orders, retention_days

celery = Celery("worker", broker=os.environ["REDIS_URL"], backend=os.environ["REDIS_URL"])
celery.conf.task_acks_late = True
celery.conf.broker_transport_options = {"socket_connect_timeout": 3}
celery.conf.beat_schedule = {
    "purge-expired-orders": {"task": "purge_expired", "schedule": 24 * 3600},
}

BATCH = 100

@celery.task(bind=True, max_retries=50)
def process_order(self, order_id: str):
    provider = get_provider()
    with SessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
        if order is None:
            return
        order.status = "processing"
        db.commit()
        while True:
            rows = db.scalars(
                select(Profile)
                .where(Profile.order_id == order.id, Profile.status == "pending")
                .order_by(Profile.id).limit(BATCH)
            ).all()
            if not rows:
                break
            for p in rows:
                r = provider.fetch(p.username)
                if r.status == "rate_limited":
                    db.commit()                       # salva o que já foi feito no lote
                    raise self.retry(countdown=300)   # tenta de novo em 5 min
                p.status = r.status
                p.followers_count = r.followers_count
                p.following_count = r.following_count
                p.bio = r.bio
            db.commit()
        order.status = "done"
        db.commit()

@celery.task(name="send_email", autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def send_email(to: str, subject: str, text: str):
    mailer.send_smtp(to, subject, text)

@celery.task(name="purge_expired")
def purge_expired():
    """Retenção: apaga pedidos mais antigos que RETENTION_DAYS (exceto em processamento)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days())
    with SessionLocal() as db:
        ids = db.scalars(
            select(Order.id).where(Order.created_at < cutoff,
                                   Order.status.notin_(("queued", "processing")))
        ).all()
        return delete_orders(db, ids)
