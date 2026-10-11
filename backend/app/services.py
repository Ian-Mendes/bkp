"""Regras de negócio: pedidos (criação, análise, enriquecimento) e retenção."""
import os, uuid
from datetime import datetime, timezone
from sqlalchemy import delete, select
from .db import SessionLocal
from .importer import parse_export
from .models import Order, Profile
from .providers import get_provider

WINDOW_DAYS = 380   # ~1 ano: indício de filtro de período no export

def retention_days() -> int:
    return int(os.getenv("RETENTION_DAYS", "30"))

def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()

def analyze(parsed, expected_followers=None, expected_following=None):
    ranges = {}
    for kind, r in parsed["ranges"].items():
        ranges[kind] = None if r is None else {
            "first": _iso(r[0]), "last": _iso(r[1]), "span_days": int((r[1] - r[0]) // 86400)}
    warnings = []
    f, g = ranges.get("followers"), ranges.get("following")
    if f and g and f["span_days"] <= WINDOW_DAYS and g["span_days"] > 2 * 365:
        warnings.append("period_window_suspected")
    coverage = {}
    for kind, expected in (("followers", expected_followers), ("following", expected_following)):
        if expected:
            found = len(parsed[kind])
            ratio = round(found / expected, 3)
            coverage[kind] = {"expected": expected, "found": found, "ratio": ratio}
            if ratio < 0.9:
                warnings.append(f"{kind}_incomplete")
    return {"ranges": ranges, "warnings": warnings, "coverage": coverage}

def create_order_from_zip(db, zip_path, filename, user_id,
                          expected_followers=None, expected_following=None):
    parsed = parse_export(zip_path)
    usernames = list(dict.fromkeys(parsed["followers"] + parsed["following"]))
    order = Order(
        user_id=user_id, source_filename=filename, status="parsed",
        followers_total=len(parsed["followers"]), following_total=len(parsed["following"]),
        invalid_count=parsed["invalid"], duplicate_count=parsed["duplicates"],
        info=analyze(parsed, expected_followers, expected_following),
    )
    db.add(order)
    db.flush()
    db.add_all(Profile(order_id=order.id, username=u) for u in usernames)
    db.commit()
    return order

def delete_orders(db, order_ids):
    """Apaga pedidos e todos os perfis deles (exclusão definitiva)."""
    order_ids = list(order_ids)
    if not order_ids:
        return 0
    db.execute(delete(Profile).where(Profile.order_id.in_(order_ids)))
    db.execute(delete(Order).where(Order.id.in_(order_ids)))
    db.commit()
    return len(order_ids)

BATCH = 100

def run_enrichment(order_id: str) -> str:
    """Enriquece os perfis pendentes de um pedido, hoje de forma síncrona.

    Com `NullProvider` a execução é instantânea. Ao ligar um provider real
    (rate limit, rede), volte a rodar numa fila (Celery) — o `rate_limited`
    abaixo marca o ponto de retry a restaurar."""
    provider = get_provider()
    with SessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
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
                    db.commit()                    # salva o progresso do lote
                    order.status = "parsed"        # sem fila de retry: volta a permitir "start"
                    db.commit()
                    return order.status
                p.status = r.status
                p.followers_count = r.followers_count
                p.following_count = r.following_count
                p.bio = r.bio
            db.commit()
        order.status = "done"
        db.commit()
        return order.status
