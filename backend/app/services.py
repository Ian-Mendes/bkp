"""Regras de negócio: pedidos (criação, análise, enriquecimento) e retenção."""
import os, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, or_
from .db import SessionLocal
from .importer import parse_export
from .models import Order, Profile, TakeoutEntry
from .providers import get_provider

WINDOW_DAYS = 380   # ~1 ano: indício de filtro de período no export
ENRICH_CACHE_DAYS = 7   # reusa perfil "ok" enriquecido há menos de uma semana
ENRICH_BATCH_SIZE = 25   # usernames por run do Apify (o actor aceita lista)

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
    followers = set(parsed["followers"])
    following = set(parsed["following"])
    order = Order(
        user_id=user_id, source_filename=filename, status="parsed",
        followers_total=len(parsed["followers"]), following_total=len(parsed["following"]),
        invalid_count=parsed["invalid"], duplicate_count=parsed["duplicates"],
        info=analyze(parsed, expected_followers, expected_following),
    )
    db.add(order)
    db.flush()
    for u in dict.fromkeys(parsed["followers"] + parsed["following"]):
        profile = db.scalar(select(Profile).where(Profile.username == u))
        if profile is None:
            profile = Profile(username=u)
            db.add(profile)
            db.flush()   # garante o perfil antes da entry que o referencia
        if u in followers:
            db.add(TakeoutEntry(order_id=order.id, username=u, relation="follower"))
        if u in following:
            db.add(TakeoutEntry(order_id=order.id, username=u, relation="following"))
    db.commit()
    return order

def delete_orders(db, order_ids):
    """Apaga pedidos e suas relações (takeout); perfis enriquecidos permanecem."""
    order_ids = list(order_ids)
    if not order_ids:
        return 0
    db.execute(delete(TakeoutEntry).where(TakeoutEntry.order_id.in_(order_ids)))
    db.execute(delete(Order).where(Order.id.in_(order_ids)))
    db.commit()
    return len(order_ids)


def _apply_result(p, r):
    """Grava um `ProfileResult` no perfil (campos já mapeados pelo provider)."""
    p.status = r.status
    p.followers_count = r.followers_count
    p.following_count = r.following_count
    p.bio = r.bio
    p.profile_url = r.profile_url
    p.full_name = r.full_name
    p.external_url = r.external_url
    p.profile_pic_url = r.profile_pic_url
    p.posts_count = r.posts_count
    p.category = r.category
    p.is_verified = r.is_verified
    p.is_business = r.is_business
    p.enrich_source = r.source
    p.enriched_at = r.fetched_at


def run_enrichment(order_id: str) -> str:
    """Enriquece os perfis pendentes de um pedido, reusando o cache de 7 dias.

    Consulta o provider apenas para perfis que precisam (nunca enriquecidos =
    `enriched_at` NULL), desatualizados (>= ENRICH_CACHE_DAYS) ou com último
    status diferente de `ok` — `not_found`/`private`/`error`. 
    
    Com `fetch_many` (Apify) envia lotes de `ENRICH_BATCH_SIZE` por run; sem ele
    (NullProvider) consulta perfil a perfil. Progresso commitado a cada perfil.
    """
    provider = get_provider()
    fetch_many = getattr(provider, "fetch_many", None)
    cutoff = datetime.now(timezone.utc) - timedelta(days=ENRICH_CACHE_DAYS)
    with SessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
        order.status = "processing"
        db.commit()
        db_query = (
            select(Profile)
            .join(TakeoutEntry, TakeoutEntry.username == Profile.username)
            .where(TakeoutEntry.order_id == order.id,
                   or_(Profile.enriched_at.is_(None),
                       Profile.enriched_at < cutoff,
                       Profile.status != "ok"))
            .distinct()
            .order_by(Profile.id)
        )
        profiles = db.scalars(db_query).all()
        if fetch_many is not None:
            for start in range(0, len(profiles), ENRICH_BATCH_SIZE):
                batch = profiles[start:start + ENRICH_BATCH_SIZE]
                results = fetch_many([p.username for p in batch])
                if results is None:            # rate_limited: volta a permitir "start"
                    order.status = "parsed"
                    db.commit()
                    return order.status
                for p in batch:
                    _apply_result(p, results[p.username])
                    db.commit()                # progresso durável e visível perfil a perfil
        else:
            for p in profiles:
                r = provider.fetch(p.username)
                if r.status == "rate_limited":
                    order.status = "parsed"
                    db.commit()
                    return order.status
                _apply_result(p, r)
                db.commit()
        order.status = "done"
        db.commit()
        return order.status

def purge_expired_orders() -> int:
    """Retenção: apaga pedidos mais antigos que RETENTION_DAYS (exceto em processamento)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days())
    with SessionLocal() as db:
        ids = db.scalars(
            select(Order.id).where(Order.created_at < cutoff,
                                   Order.status.notin_(("queued", "processing")))
        ).all()
        return delete_orders(db, ids)
