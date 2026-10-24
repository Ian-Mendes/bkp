"""Celery worker: task assíncrona de enriquecimento de perfis."""
import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded

from .celery_app import celery
from . import services
from .models import Order

log = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=660)
def process_order(self, order_id: str) -> str:
    """Enriquece os perfis de um pedido.

    Idempotente: re-execuções não duplicam enriquecimento (o cache de 7 dias do
    `run_enrichment` filtra perfis atualizados). Em `rate_limited` ou estouro do
    `soft_time_limit`, reagenda com backoff exponencial (60s → 120s → 240s);
    após esgotar, marca `failed`.
    """
    try:
        status = services.run_enrichment(order_id)
    except SoftTimeLimitExceeded:
        # Progresso já commitado perfil a perfil; reagenda para continuar de onde parou.
        if self.request.retries >= self.max_retries:
            _update_status(order_id, "failed", error="timeout")
            raise
        _update_status(order_id, "queued")
        raise self.retry(countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _update_status(order_id, "failed", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
        _update_status(order_id, "queued")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    if status == "parsed":
        # `run_enrichment` só retorna "parsed" no caminho de rate_limited
        if self.request.retries >= self.max_retries:
            _update_status(order_id, "failed", error="rate_limited")
            return "failed"
        _update_status(order_id, "queued")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

    return status


def _update_status(order_id: str, status: str, error: str | None = None) -> None:
    """Atualiza o status do pedido fora do fluxo do `run_enrichment`.

    Usa `services.SessionLocal` para que os testes possam interceptar via
    `monkeypatch.setattr(services, "SessionLocal", Session)` (o `conftest.py`
    já faz isso).
    """
    with services.SessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
        if order is None:
            return
        order.status = status
        if error is not None:
            info = order.info or {}
            info["error"] = error
            order.info = info
        db.commit()
