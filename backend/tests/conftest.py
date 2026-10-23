import os

# Variáveis de ambiente para testes (executados fora do Docker)
os.environ.setdefault("JWT_SECRET", "segredo-de-teste-apenas-para-pytest-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")   # <-- ADICIONADO
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import main, rate, auth, services
from tests.helpers import OUTBOX

REAL_ENQUEUE = auth.enqueue_email   # a fixture abaixo troca por um fake; os testes de fila usam o real
from app.db import Base, get_db
from app.main import app

@pytest.fixture(autouse=True)
def fake_rate(monkeypatch):
    counts = {}
    def hit(key, limit, window):
        counts[key] = counts.get(key, 0) + 1
        return counts[key] <= limit
    monkeypatch.setattr(rate, "hit", hit)

@pytest.fixture(autouse=True)
def fake_email(monkeypatch):
    OUTBOX.clear()
    monkeypatch.setattr(auth, "enqueue_email",
                        lambda bg, to, subject, text: OUTBOX.append((to, subject, text)))

@pytest.fixture(autouse=True)
def fake_celery(monkeypatch):
    """Impede que `.delay()` tente conectar no Redis durante os testes.

    Retorna uma lista com os `order_id` enfileirados. Testes que precisam do
    efeito do enriquecimento chamam `services.run_enrichment` diretamente
    (padrão já usado em `test_worker_processa_tudo`).
    """
    from app import worker
    enqueued = []

    def fake_delay(order_id):
        enqueued.append(order_id)
        return None

    monkeypatch.setattr(worker.process_order, "delay", fake_delay)
    return enqueued

@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(main, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(services, "SessionLocal", Session)
    yield TestClient(app), Session, tmp_path
    app.dependency_overrides.clear()
