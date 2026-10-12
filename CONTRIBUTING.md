# Contribuindo

Obrigado pelo interesse em contribuir com o BKP. Aqui está como rodar, testar
e propor mudanças.

## Como começar

1. `cp .env.example .env` e preencha `POSTGRES_PASSWORD`, `DATABASE_URL`
   (senhas idênticas) e um `JWT_SECRET` de 32+ caracteres. O passo a passo
   completo está no `README.md`.
2. `docker compose up -d --build` — sobe a API (:8000), o Mailpit (:8025) e o
   frontend de dev (:3000, via `docker-compose.override.yml`).
3. `docker compose exec api pytest` — confirme que o ambiente está saudável.

> Rode tudo dentro do Docker (`docker compose exec`). Não rode `pytest`/`pip`/
> `npm` direto na máquina.

## Onde começar a ler

- `README.md` — manual de operação completo.
- `backend/app/main.py` → `services.py` → `importer.py` — o único fluxo de
  ponta a ponta que funciona hoje (upload → parse → relatório).
- `backend/tests/test_api.py` — documentação viva do fluxo upload →
  enriquecimento → export.
- `AGENTS.md` (raiz, `backend/` e `frontend/`) — regras e convenções para
  agentes de IA e contribuidores.

## Primeira mudança de valor

- **Provider real de enriquecimento:** criar
  `backend/app/providers/apify_provider.py` satisfazendo `ProfileProvider.fetch`
  e registrá-lo em `get_provider()` — as variáveis `APIFY_TOKEN`/`APIFY_ACTOR_ID`
  e os estados de `Profile.status` já estão preparados.
- **Frontend de pedidos:** construir upload/lista/download sobre os endpoints
  `/orders`, usando `src/lib/api.js`.

## Fluxo de trabalho

1. Abra uma issue (ou escolha uma existente) e descreva o que vai fazer.
2. Crie uma branch: `git checkout -b feat/nome-da-feature`.
3. Faça commits pequenos e descritivos, explicando o "porquê".
4. Rode `docker compose exec api pytest` antes de abrir o PR.
5. Abra o PR com o template de `.github/PULL_REQUEST_TEMPLATE.md` e referencie a
   issue (`Closes #N`).

## Convenções

- Documentação, comentários e textos de UI em pt-BR; código (identificadores,
  status HTTP, comandos) em inglês.
- Contadores desconhecidos ficam `NULL`, nunca `0`.
- Respeite as camadas e reutilize o que já existe — veja `AGENTS.md`.

## Precisa de ajuda?

Abra uma issue. E nunca peça nem compartilhe a senha do Instagram de ninguém.
