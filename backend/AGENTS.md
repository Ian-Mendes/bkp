# AGENTS.md — Backend

Complementa o `AGENTS.md` raiz.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · Celery + Redis ·
APScheduler · PyJWT + Argon2 · openpyxl · pytest (SQLite em memória nos testes).

Sem e-mail: acesso por convite gerado no backoffice (`python -m app.invite`).
O enriquecimento roda no worker Celery; a retenção roda no agendador do `main.py`.

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
| `main.py` | App FastAPI, lifespan (agendador de retenção), middleware de segurança, rotas `/orders`. |
| `auth.py` | Rotas `/auth`: login, aceite de convite, sessão e revogação. |
| `invite.py` | Comando de backoffice: gera links de convite de uso único. |
| `services.py` | Convites (`create_invite`/`accept_invite`), pedidos, `run_enrichment` (lote + commit por perfil), `purge_expired_orders`. |
| `importer.py` | Parser do Takeout (JSON + HTML) + guardas de ZIP bomb. |
| `exporter.py` | CSV/XLSX + anti-injeção (`safe`). |
| `rate.py` | Rate limiting em janela fixa, em memória. |
| `worker.py` | Task Celery `process_order` (enriquecimento assíncrono). |

## Comandos

```bash
docker compose exec api pytest
docker compose exec api pytest tests/test_auth.py::test_convite_aceito_autentica_e_login
docker compose exec api pytest -k importer -q
docker compose exec api python -c "import app.main"
docker compose exec api python -m app.invite a@b.com
```

## Testes

- `tests/`: `test_api.py`, `test_auth.py`, `test_importer.py`, `test_security.py`,
  `test_orders_access.py`, `test_worker.py`, `test_apify_provider.py`.
- `conftest.py`: `fake_rate` (autouse) e `fake_celery` (autouse); `env` sobe
  SQLite em memória, sobrescreve `get_db`, redireciona `main.UPLOAD_DIR` e
  religa `services.SessionLocal`. Retorna `(client, Session, tmp_path)`.
- `helpers.py`: `make_zip`, `make_zip_html`, `invite`, `register`, `upload`.
- Sem cobertura/linter — teste o invariante, não só o caminho feliz.

## Invariantes de segurança (não regredir)

- Acesso só por convite de uso único (token hasheado, expira em `INVITE_DAYS`);
  sem auto-cadastro; sessão com fingerprint de senha (`security.py`).
- Convite não vale como sessão; `accept-invite` com rate limit e resposta única
  para inválido/expirado/usado.
- `exporter.safe` em toda célula; `no-store` em `/auth` e `/orders`; headers em tudo.
- Rate limit (`rate.py`), limite de corpo (`main.py`) e guardas de ZIP bomb
  (`importer.py`) permanecem. `JWT_SECRET` ≥ 32 caracteres.

## Playbooks

- Novo endpoint: `current_user` + `get_db`, `_get_order` p/ ownership (404), teste.
- Novo provider: `fetch() -> ProfileResult` (e, se fizer sentido, `fetch_many()`
  para lote); o `rate_limited` volta a `parsed` em `services.run_enrichment`.
- Schema: edite `models.py`, rode `alembic revision --autogenerate`, revise e
  `alembic upgrade head` (nunca `create_all`/`ALTER` manual).
- Convite: `create_invite`/`accept_invite` em `services.py`; o comando CLI fica
  em `invite.py`.

## Armadilhas

- Alembic versiona o schema; `create_all` não altera tabelas existentes.
- `with_for_update` é no-op no SQLite.
- Rate limit em memória: zera no restart, single-instance. Agendador de retenção
  também (single-instance).
- Datetimes no SQLite perdem tz: compare em SQL, não em Python.
- Dependências sem pin; upload apagado após parsing (salvo `KEEP_UPLOADS=1`).
