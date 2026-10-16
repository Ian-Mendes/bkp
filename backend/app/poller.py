"""Worker de enriquecimento sem broker: polling no Postgres.

Substitui a chamada síncrona de `POST /start` (que estourava o timeout em
pedidos grandes — ver issue #14). A \"fila\" é o próprio `Order.status`:
`queued` → `processing` → `done`/`failed`. Sem Redis/Celery, sem migração.

- Um worker por vez no MVP (o claim com `SKIP LOCKED` evita duplo consumo
  se um segundo subir por engano).
- Queda no meio do lote: no boot, `processing` órfão volta a `queued` e o
  `run_enrichment` retoma pelos `pending` — nada é refeito.
- Erro inesperado nunca derruba o loop; o pedido problemático volta a
  `failed` para inspeção e re-`start` manual.
"""
import logging
import time

from . import services

POLL_SECS = 5   # intervalo sem pedido na fila

log = logging.getLogger("poller")


def run_once() -> str | None:
    """Processa um pedido `queued`. Retorna o status final ou None (fila vazia)."""
    with services.SessionLocal() as db:
        order_id = services.claim_queued_order(db)
    if order_id is None:
        return None
    try:
        return services.run_enrichment(str(order_id))
    except Exception:
        log.exception("pedido %s falhou; marcando failed", order_id)
        with services.SessionLocal() as db:
            if order := db.get(services.Order, order_id):
                order.status = "failed"
                db.commit()
        return "failed"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with services.SessionLocal() as db:
        orphans = services.requeue_orphans(db)
    if orphans:
        log.info("%d pedido(s) órfão(s) de volta à fila", orphans)
    log.info("poller no ar")
    while True:
        try:
            done = run_once()
        except Exception:
            log.exception("falha fora do pedido; próximo ciclo retenta")
            done = "failed"
        if done is None:
            time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
