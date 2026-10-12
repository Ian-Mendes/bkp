# AGENTS.md — Backend

Complementa o `AGENTS.md` raiz.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · APScheduler · PyJWT +
Argon2 · openpyxl · pytest (SQLite em memória nos testes).

Sem Celery/Redis no MVP: e-mail roda em `BackgroundTasks`, o enriquecimento é
síncrono e a retenção roda no agendador do `main.py`.

## Regras de ouro

- Comentários/docstrings em pt-BR; identificadores em inglês. Comente o "porquê".
- Todo módulo abre com docstring: o que faz, o porquê e quando trocar por outra solução.
- Contadores desconhecidos ficam `NULL` — nunca `0`.
- Erros de domínio: `importer.ExportError` → HTTP 400 (mensagem segura, sem traceback).
- Código enxuto; funções curtas; nada de abstração prematura.
- Rode `pytest` após cada mudança.

## Estrutura (obrigatória)

- Camadas: HTTP (`main.py`, `auth.py`) → domínio (`services.py`, `importer.py`,
  `exporter.py`) → persistência (`models.py`, `db.py`). Handlers finos.
- Reuse: `_get_order`, `exporter.safe`, `rate.hit`, `get_db`, `current_user`.
- Providers: Protocol em `providers/base.py`, registrados em `get_provider()`.
- SQLAlchemy 2.0 (`Mapped[...]`); corpos de request em Pydantic.

## Onde cada responsabilidade vive

| Módulo | Responsabilidade |
|---|---|
| `main.py` | App FastAPI, lifespan (create_all + `ALTER` + agendador de retenção), middleware de segurança, rotas `/orders`. |
| `auth.py` | Rotas `/auth`; e-mail via `BackgroundTasks` (`enqueue_email`). |
| `services.py` | Criação de pedido, análise de integridade, `run_enrichment` (síncrono), `purge_expired_orders`. |
| `importer.py` | Parser do Takeout (JSON + HTML) + guardas de ZIP bomb. |
| `exporter.py` | CSV/XLSX + anti-injeção (`safe`). |
| `rate.py` | Rate limiting em janela fixa, em memória. |
| `worker.py` | Stub comentado (scaffolding da fila — não remover). |

## Comandos

```bash
docker compose exec api pytest
docker compose exec api pytest tests/test_auth.py::test_recuperar_senha
docker compose exec api pytest -k importer -q
docker compose exec api python -c "import app.main"
```

## Testes

- `tests/`: `test_api.py`, `test_auth.py`, `test_email.py`, `test_importer.py`,
  `test_security.py`, `test_orders_access.py`.
- `conftest.py`: `fake_rate` (autouse) e `fake_email` (autouse) substituem o
  rate limit e o `enqueue_email`; `env` sobe SQLite em memória, sobrescreve
  `get_db`, redireciona `main.UPLOAD_DIR` e religa `services.SessionLocal`.
  Retorna `(client, Session, tmp_path)`.
- `helpers.py`: `make_zip`, `make_zip_html`, `register`, `upload`, `last_token`.
- Sem cobertura/linter — teste o invariante, não só o caminho feliz.

## Invariantes de segurança (não regredir)

- Anti-enumeração; sessão com fingerprint de senha (`security.py`); tokens com
  propósito (verify/reset) não valem como sessão.
- `exporter.safe` em toda célula; `no-store` em `/auth` e `/orders`; headers em tudo.
- Rate limit (`rate.py`), limite de corpo (`main.py`) e guardas de ZIP bomb
  (`importer.py`) permanecem. `JWT_SECRET` ≥ 32 caracteres.

## Playbooks

- Novo endpoint: `current_user` + `get_db`, `_get_order` p/ ownership (404), teste.
- Novo provider: `fetch() -> ProfileResult`; o `rate_limited` volta a `parsed`
  em `services.run_enrichment` (sem fila de retry no MVP).
- Schema: atualize `models.py` **e** o `ALTER TABLE` manual (`main.py`, lifespan).

## Armadilhas

- Sem Alembic; `create_all` não altera tabelas existentes.
- `with_for_update` é no-op no SQLite.
- Rate limit em memória: zera no restart, single-instance. Agendador de retenção
  também (single-instance).
- Dependências sem pin; `PROVIDER` só aceita `null`. Upload apagado após parsing
  (salvo `KEEP_UPLOADS=1`).
