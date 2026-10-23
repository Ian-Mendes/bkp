# AGENTS.md

Regras para agentes de IA e engenheiros neste repositório. `backend/AGENTS.md`
e `frontend/AGENTS.md` complementam este arquivo com o que muda em cada lado.

## O que é

BKP converte a exportação (Takeout) do Instagram em planilha enriquecida
CSV/XLSX. Backend FastAPI + SQLAlchemy, frontend Vite + React. O enriquecimento
real ainda é um stub (`NullProvider`); sem fila (Celery/Redis) no MVP.

- Produto e operação: `README.md`. Infra: `docker-compose.yml` (+ `docker-compose.override.yml` em dev).
- Contribuição: `CONTRIBUTING.md`. Template de PR: `.github/PULL_REQUEST_TEMPLATE.md`.

## Princípios

1. **Alcance mínimo.** A menor edição que resolve; siga o estilo ao redor.
2. **Enxuto.** Comente só o "porquê" não óbvio. Sem comentário que repete o
   código, sem código morto, sem TODO órfão, sem abstração prematura.
3. **Idioma.** Comentários, docstrings, docs e textos de UI em pt-BR.
   Identificadores, caminhos, comandos, status HTTP e termos técnicos em inglês.
4. **Reuse.** Prefira o que já existe a criar arquivo, pasta ou camada novos.

## Limites operacionais

- Nunca commite `.env`; nunca peça nem guarde a senha do Instagram.
- Arquivos de rotina, rascunhos, planos e documentação avulsa vão em `tmp/`
  (pasta gitignored) — nunca no repositório.
- Nunca rode `pytest`/`pip`/`npm` direto na máquina — sempre em container
  (`docker compose exec`).
- **Exceção temporária:** o código comentado de Celery/Redis em
  `backend/app/worker.py`, `backend/requirements.txt`, `docker-compose.yml` e
  `backend/tests/conftest.py` é scaffolding para reintroduzir a fila quando o
  provider real (Apify) chegar. Não remova.

## Ambiente
- **Alembic:** o banco é versionado em `backend/alembic/`. Em dev, se o
  schema estiver desatualizado, `docker compose exec api alembic upgrade head`.
- `cp .env.example .env`.
- `JWT_SECRET` com ≥ 32 caracteres (validado no import do backend).
- `POSTGRES_PASSWORD` idêntica à senha dentro de `DATABASE_URL` (o Postgres só lê a senha ao criar o volume).

## Estrutura (obrigatória)

Respeite as camadas; regra de negócio fica fora do handler:

- **HTTP:** `main.py`, `auth.py` — handlers finos.
- **Domínio:** `services.py`, `importer.py`, `exporter.py`.
- **Persistência:** `models.py`, `db.py`.
- **Providers:** `providers/base.py` (Protocol) + `get_provider()`.

Reuse antes de criar: `_get_order` (ownership), `exporter.safe` (células),
`rate.hit` (limites), `get_db`, `current_user`.

## Testes

```bash
docker compose exec api pytest
docker compose exec api pytest tests/test_auth.py::test_recuperar_senha
docker compose exec api pytest -k importer -q
```

Rode `pytest` após qualquer mudança no backend. Não há suíte no frontend.

## Convenções-chave

- **Contadores desconhecidos ficam `NULL`, nunca `0`** — o export renderiza
  `NULL` como célula vazia.

  ```python
  # Errado
  followers_count: Mapped[int] = mapped_column(Integer, default=0)

  # Certo
  followers_count: Mapped[int | None] = mapped_column(Integer)   # NULL = não consultado
  ```

- **Erros de domínio:** `importer.ExportError` → HTTP 400 com mensagem segura;
  nunca vazar traceback.
- **`exporter.safe` em toda célula** (neutraliza injeção de fórmula e limpa
  caracteres de controle).

## Invariantes de segurança (não regredir)

- Anti-enumeração em `register`/`resend`/`forgot` (mesma resposta, exista ou
  não o e-mail).
- `no-store` em `/auth` e `/orders`; headers de segurança em toda resposta.
- Isolamento por usuário, rate limit e guardas de ZIP bomb (`importer.py`).
- Sessão em cookie httpOnly (`bkp_session`) + refresh (`bkp_refresh`); `token_version`
  permite revogação em massa (logout, troca de senha).
- Tokens de e-mail (verify/reset) não valem como sessão.

## Playbooks

- **Novo endpoint:** `current_user` + `get_db`; `_get_order` para ownership
  (responder 404, nunca 403); teste em `tests/`.
- **Novo provider:** `fetch(username) -> ProfileResult`, registre em
  `get_provider()`, teste com `fetch` mockado.
- **Mudança de schema:** edite `models.py`, rode `docker compose exec api
  alembic revision --autogenerate -m "descrição curta"`, revise o arquivo em
  `backend/alembic/versions/` (o autogenerate erra defaults, FKs e enums com
  frequência) e aplique com `docker compose exec api alembic upgrade head`.
  Nunca use `create_all` nem `ALTER TABLE` manual em `main.py`.
## Armadilhas

- **Alembic:** o schema é versionado. Mudanças em `models.py` exigem uma
  revisão (`alembic revision --autogenerate`) + `alembic upgrade head`. Sem
  `create_all` no boot. O banco de dev pode ser recriado com `docker compose
  down -v` para aplicar do zero.
- `.env` exige `docker compose up -d --force-recreate` para reler.
- Rate limit é em memória (`rate.py`): zera no restart e não é compartilhado
  entre réplicas (single-instance). Idem o agendador de retenção (APScheduler).
- `PROVIDER` só aceita `null`; `requirements.txt` sem pin.
- O frontend **não guarda token** no JS: usa cookie httpOnly com `credentials: "include"`.
  Não reintroduza `localStorage` (`bkp_token`) para sessão.

## Verifique antes de terminar

- [ ] `docker compose exec api pytest` verde.
- [ ] Comentários, docstrings e docs em pt-BR.
- [ ] `.env.example` atualizado se surgir variável nova.
- [ ] `README.md` atualizado se um item do roadmap foi concluído.
