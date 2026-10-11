import os
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import select
from .db import SessionLocal
from .models import Order
from .services import delete_orders, retention_days

celery = Celery("worker", broker=os.environ["REDIS_URL"], backend=os.environ["REDIS_URL"])
celery.conf.task_acks_late = True
celery.conf.broker_transport_options = {"socket_connect_timeout": 3}
celery.conf.beat_schedule = {
    "purge-expired-orders": {"task": "purge_expired", "schedule": 24 * 3600},
}

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
