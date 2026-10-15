import csv, io, re
from openpyxl import Workbook
from sqlalchemy import select, func, or_, case, and_
from .models import Profile

COLUMNS = ["username", "tipo", "followers_count", "following_count", "bio", "status"]
SORTS = {"followers_count": Profile.followers_count,
         "following_count": Profile.following_count,
         "username": Profile.username}
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_FORMULA = ("=", "+", "-", "@", "\t", "\r")

def safe(v):
    """Remove caracteres ilegais e neutraliza injeção de fórmula em planilhas."""
    if isinstance(v, str):
        v = _ILLEGAL.sub("", v)
        if v[:1] in _FORMULA:
            v = "'" + v
    return v

def tipo(p):
    """Relação do perfil com o dono do pedido, em uma coluna legível no backup."""
    if p.is_follower and p.is_following:
        return "ambos"
    if p.is_follower:
        return "seguidor"
    if p.is_following:
        return "seguindo"
    return ""

def row(p):
    return [safe(x) for x in (p.username, tipo(p), p.followers_count,
                              p.following_count, p.bio, p.status)]

def query_profiles(order_id, sort_by="followers_count", direction="desc", q=None):
    stmt = select(Profile).where(Profile.order_id == order_id)
    terms = [t.strip() for t in (q or "").split(",") if t.strip()]
    if terms:
        stmt = stmt.where(or_(*[Profile.bio.ilike(f"%{t}%") for t in terms]))
    col = SORTS.get(sort_by, Profile.followers_count)
    col = col.asc().nulls_last() if direction == "asc" else col.desc().nulls_last()
    return stmt.order_by(col, Profile.username)

def build_report(db, order):
    base = Profile.order_id == order.id
    total = db.scalar(select(func.count()).select_from(Profile).where(base)) or 0
    by_status = dict(db.execute(
        select(Profile.status, func.count()).where(base).group_by(Profile.status)).all())
    coverage = {}
    for name, col in (("followers_count", Profile.followers_count),
                      ("following_count", Profile.following_count),
                      ("bio", Profile.bio)):
        filled = db.scalar(select(func.count(col)).where(base)) or 0
        coverage[name] = {"filled": filled, "total": total,
                          "pct": round(100 * filled / total, 1) if total else 0}
    rel = db.execute(select(
        func.sum(case((and_(Profile.is_follower, ~Profile.is_following), 1), else_=0)),
        func.sum(case((and_(~Profile.is_follower, Profile.is_following), 1), else_=0)),
        func.sum(case((and_(Profile.is_follower, Profile.is_following), 1), else_=0)),
    ).where(base)).one()
    by_relationship = {"follower": rel[0] or 0, "following": rel[1] or 0, "both": rel[2] or 0}
    return {"order_id": str(order.id), "status": order.status, "total_profiles": total,
            "followers_in_file": order.followers_total, "following_in_file": order.following_total,
            "invalid": order.invalid_count, "duplicates": order.duplicate_count,
            "by_status": by_status, "by_relationship": by_relationship,
            "field_coverage": coverage, "export_info": order.info or {}}

def summary_rows(rep):
    rows = [("Resumo do pedido", ""), ("Perfis únicos", rep["total_profiles"]),
            ("Seguidores no arquivo", rep["followers_in_file"]),
            ("Seguindo no arquivo", rep["following_in_file"]),
            ("seguem você", rep["by_relationship"]["follower"]),
            ("você segue", rep["by_relationship"]["following"]),
            ("ambos", rep["by_relationship"]["both"]),
            ("Registros inválidos", rep["invalid"]), ("Duplicados removidos", rep["duplicates"])]
    for s, n in rep["by_status"].items():
        rows.append((f"status: {s}", n))
    for f, c in rep["field_coverage"].items():
        rows.append((f"preenchido: {f}", f"{c['filled']}/{c['total']} ({c['pct']}%)"))
    info = rep["export_info"]
    for k, c in (info.get("coverage") or {}).items():
        rows.append((f"cobertura {k}", f"{c['found']}/{c['expected']} ({round(c['ratio'] * 100, 1)}%)"))
    for w in info.get("warnings", []):
        rows.append(("aviso", w))
    return rows

def to_csv(profiles):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for p in profiles:
        w.writerow(["" if v is None else v for v in row(p)])   # NULL vira vazio, nunca 0
    return ("\ufeff" + buf.getvalue()).encode("utf-8")

def to_xlsx(profiles, rep):
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Perfis")
    ws.append(COLUMNS)
    for p in profiles:
        ws.append(row(p))
    rs = wb.create_sheet("Resumo")
    for r in summary_rows(rep):
        rs.append(list(r))
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
