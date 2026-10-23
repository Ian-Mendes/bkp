"""Instância Celery compartilhada entre API e worker.

Aqui centralizamos broker/backend (Redis) e configurações de confiabilidade:
`task_acks_late` + `task_reject_on_worker_lost` garantem re-entrega se o worker
cair no meio da task; a idempotência fica com `services.run_enrichment` (o cache
de 7 dias filtra perfis já atualizados, então re-executar é seguro e barato).
"""
import os

from celery import Celery

celery = Celery(
    "worker",
    broker=os.environ["REDIS_URL"],
    backend=os.environ["REDIS_URL"],
)

celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # dispatch justo: worker pega 1 task por vez
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
