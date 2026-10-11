# BKP — SaaS de Backup Enriquecido do Instagram

Plataforma que recebe o arquivo de exportação (Takeout) do Instagram,
extrai a rede de seguidores/seguindo do titular, enriquece cada perfil
com dados públicos (seguidores, seguindo, bio) e entrega uma planilha
normalizada em CSV/XLSX pronta para filtrar, segmentar e usar.

> **Inspiração de produto:** [Segue No Insta](https://seguenoinsta.nucleodigital.cc/)
> **Referência legal:** LGPD (ANPD), Termos da Meta/Instagram

---

## Status Atual do Projeto

| Componente | Status |
|------------|--------|
| Parser JSON (Takeout) | ✅ Funcionando |
| Parser HTML (Takeout) | ✅ Funcionando |
| Normalização e deduplicação | ✅ Funcionando |
| Análise de integridade (janelas, cobertura) | ✅ Funcionando |
| Autenticação (JWT + Argon2) | ✅ Funcionando |
| Confirmação de e-mail e recuperação de senha | ✅ Funcionando (Mailpit em dev) |
| Frontend: login, cadastro, confirmação e recuperação de senha | ✅ Funcionando |
| Isolamento entre clientes | ✅ Testado |
| Retenção e exclusão (LGPD) | ✅ Implementado |
| Fila assíncrona (Celery + Redis) | ✅ Pronto |
| Exportação CSV/XLSX | ✅ Implementado |
| **Enriquecimento (provider real)** | ⏳ **Pendente** — usando `NullProvider` |
| Frontend: upload, pedidos e downloads | ⏳ Não iniciado |

---

## Stack

**Backend**
- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy + PostgreSQL 16
- Celery + Redis 7
- PyJWT + argon2-cffi
- openpyxl (XLSX)
- httpx, python-multipart, pydantic-settings, email-validator
- pytest (52 testes)

**Infraestrutura**
- Docker + Docker Compose
- Armazenamento privado de arquivos (volume local; S3 na produção)
- Mailpit (SMTP de desenvolvimento, captura os e-mails)

**Frontend**
- Next.js 14 (App Router, JavaScript)

---

## Estrutura do Projeto

```
bkp/
├── README.md
├── docker-compose.yml
├── .env.example
├── frontend/
│   ├── Dockerfile
│   ├── next.config.js         # Cabeçalhos de segurança (CSP etc.)
│   ├── lib/api.js             # Cliente da API + token
│   └── app/
│       ├── login/             # Entrar / cadastrar
│       ├── verify-email/      # Confirmação de e-mail
│       ├── forgot-password/   # Pedir link de redefinição
│       ├── reset-password/    # Definir nova senha
│       └── dashboard/         # Área logada (provisória)
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── app/
    │   ├── main.py            # API FastAPI
    │   ├── worker.py          # Tarefas Celery
    │   ├── importer.py        # Parser do Takeout (JSON + HTML)
    │   ├── services.py        # Regras de negócio
    │   ├── exporter.py        # CSV/XLSX
    │   ├── models.py          # SQLAlchemy
    │   ├── auth.py            # Cadastro, login, confirmação de e-mail, recuperação de senha
    │   ├── security.py        # Hash + JWT (sessão e tokens de e-mail)
    │   ├── mailer.py          # Envio SMTP
    │   ├── rate.py            # Rate limiting
    │   └── providers/         # Fontes de enriquecimento
    │       ├── base.py
    │       ├── null_provider.py
    │       └── (futuro) apify_provider.py
    ├── tests/                 # pytest (API, auth, e-mail, segurança, importer)
    └── tools/                 # Scripts de análise e debug (count_files, dates)
```

---

## Como Rodar (Docker)

```bash
# 1. Clonar
git clone https://github.com/Ian-Mendes/bkp.git
cd bkp

# 2. Configurar variáveis (no PowerShell: Copy-Item .env.example .env)
cp .env.example .env
# Editar .env: POSTGRES_PASSWORD, a mesma senha no DATABASE_URL e um JWT_SECRET

# 3. Subir
docker compose up -d --build

# 4. Rodar testes
docker compose exec api pytest

# 5. Health check
curl http://localhost:8000/health
```

Serviços e portas (todos só em localhost):

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API (Swagger em `/docs`, só em desenvolvimento) | http://localhost:8000 |
| Mailpit (e-mails capturados) | http://localhost:8025 |

Notas:
- O `JWT_SECRET` precisa ter 32+ caracteres e `POSTGRES_PASSWORD` deve ser igual à senha dentro do `DATABASE_URL`. Use só letras e números na senha.
- O Postgres só lê `POSTGRES_PASSWORD` ao criar o volume. Se trocar a senha depois, rode `docker compose down -v` (apaga o banco).
- Mudou o `.env`? `docker compose restart` não relê o arquivo: use `docker compose up -d --force-recreate`.
- `worker` e `beat` não têm hot reload: após mudar o código deles, `docker compose restart worker beat`.
- Mudou o `package.json` do frontend? `docker compose up -d --build frontend`.
- O login só funciona depois de confirmar o e-mail (veja a seção abaixo).

### Testar confirmação de e-mail e recuperação de senha

Em desenvolvimento nenhum e-mail sai de verdade. Cadastre-se em http://localhost:3000 e abra
o Mailpit em http://localhost:8025 para clicar no link recebido.

- **Confirmação:** o link abre `/verify-email`, que pede a **senha do cadastro** para ativar a conta.
- **Recuperação:** em "Esqueci minha senha" informe o e-mail; o link do Mailpit vale 30 min e só funciona uma vez.
- **Não chegou e-mail?** Veja `docker compose logs worker --tail 30` (tarefa `send_email`).
- Cada fluxo (cadastro, reenvio, recuperação) envia no máximo 6 e-mails por hora para o mesmo endereço.

### Resetar os dados

```bash
# Apagar tudo (banco, uploads e e-mails do Mailpit)
docker compose down -v && docker compose up -d

# Só usuários, pedidos e perfis
docker compose exec db psql -U app -d backup -c "TRUNCATE users, orders, profiles RESTART IDENTITY CASCADE;"

# Zerar limites de tentativas (rate limit) e fila
# (se o Redis tiver senha: redis-cli -a "$REDIS_PASSWORD" FLUSHALL)
docker compose exec redis redis-cli FLUSHALL
```

---

## Variáveis de Ambiente (`.env`)

```env
# Banco
POSTGRES_PASSWORD=troque_esta_senha
DATABASE_URL=postgresql+psycopg://app:troque_esta_senha@db:5432/backup

# Fila
REDIS_URL=redis://redis:6379/0       # com senha: redis://:SENHA@redis:6379/0
REDIS_PASSWORD=                      # opcional em dev; use em produção (igual à do REDIS_URL)

# Segurança (mínimo 32 caracteres)
JWT_SECRET=troque_por_uma_string_aleatoria_com_32_mais_caracteres
TOKEN_MINUTES=60                     # duração da sessão (padrão 60; opcional)

# Uploads
MAX_UPLOAD_MB=200
KEEP_UPLOADS=0

# Retenção (dias)
RETENTION_DAYS=30

# CORS
CORS_ORIGINS=http://localhost:3000

# Provider de enriquecimento
PROVIDER=null          # null | apify
APIFY_TOKEN=           # preencher quando implementar
APIFY_ACTOR_ID=apify/instagram-profile-scraper

# E-mail (dev: Mailpit; em produção use um provedor SMTP real)
FRONTEND_URL=http://localhost:3000   # base dos links enviados por e-mail
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_STARTTLS=0                      # 1 em provedores com STARTTLS
MAIL_FROM=BKP <no-reply@bkp.local>

# Segurança / produção
APP_ENV=development        # production: ativa HSTS e desativa /docs (a menos que ENABLE_DOCS=1)
ENABLE_DOCS=1              # 0 desativa /docs, /redoc e /openapi.json
UPLOADS_PER_HOUR=10        # envios de ZIP por usuário por hora
MAX_ORDERS_PER_USER=20     # pedidos guardados por usuário
```

Os valores de e-mail e de segurança têm padrão no código (Mailpit, desenvolvimento); só precisam estar no `.env` para mudar.

O frontend lê `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`); ver `frontend/.env.example`.

**Nunca comite o `.env` real.** Use `.env.example` como modelo.

---

## Fluxo de Uso da API

```bash
# 1. Registrar (envia um e-mail de confirmação; não devolve token)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@exemplo.com","password":"senha-bem-longa-123"}'

# 2. Confirmar o e-mail (token do link recebido, em dev veja no Mailpit, e a senha do cadastro)
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token":"...","password":"senha-bem-longa-123"}'

# 3. Fazer login (guarda o token). Sem confirmar o e-mail, retorna 403.
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@exemplo.com","password":"senha-bem-longa-123"}'
TOKEN="..."

# 4. Enviar o ZIP do Takeout
curl -X POST http://localhost:8000/orders \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@takeout.zip"

# 5. Iniciar o enriquecimento
curl -X POST http://localhost:8000/orders/$ORDER_ID/start \
  -H "Authorization: Bearer $TOKEN"

# 6. Acompanhar
curl http://localhost:8000/orders/$ORDER_ID \
  -H "Authorization: Bearer $TOKEN"

# 7. Baixar relatório
curl http://localhost:8000/orders/$ORDER_ID/report \
  -H "Authorization: Bearer $TOKEN"

# 8. Baixar planilhas
curl -o backup.csv  http://localhost:8000/orders/$ORDER_ID/export.csv  -H "Authorization: Bearer $TOKEN"
curl -o backup.xlsx http://localhost:8000/orders/$ORDER_ID/export.xlsx -H "Authorization: Bearer $TOKEN"
```

Recuperação de senha:

```bash
# Pede o link (resposta sempre igual, exista ou não o e-mail)
curl -X POST http://localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" -d '{"email":"voce@exemplo.com"}'

# Define a nova senha com o token do link (mínimo 10 caracteres)
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token":"...","password":"nova-senha-bem-longa-456"}'
```

Códigos úteis: `401` token inválido ou senha errada, `403` e-mail não confirmado, `413` corpo grande demais,
`429` limite de tentativas, `409` limite de pedidos guardados por usuário.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/auth/register` | Cadastro (envia e-mail de confirmação; não devolve token) |
| POST | `/auth/verify-email` | Confirma o e-mail (token do link + senha do cadastro) |
| POST | `/auth/resend-verification` | Reenvia a confirmação |
| POST | `/auth/login` | Login (403 se o e-mail não foi confirmado) |
| POST | `/auth/forgot-password` | Envia link de redefinição de senha |
| POST | `/auth/reset-password` | Define a nova senha com o token do link |
| GET | `/auth/me` | Dados do usuário |
| POST | `/orders` | Upload do ZIP |
| GET | `/orders` | Lista pedidos |
| GET | `/orders/{id}` | Detalhe do pedido |
| POST | `/orders/{id}/start` | Iniciar processamento |
| DELETE | `/orders/{id}` | Excluir pedido |
| GET | `/orders/{id}/report` | Relatório em JSON |
| GET | `/orders/{id}/export.csv` | Download CSV |
| GET | `/orders/{id}/export.xlsx` | Download XLSX |

---

## Ferramentas de Desenvolvimento

Rode de dentro de `backend/`:

```bash
# Contar usuários em um ZIP de teste
python3 -m tools.count_files ../dados_insta_exportados_json.zip

# Analisar janelas de datas do Takeout
python3 -m tools.dates ../dados_insta_exportados_json.zip
```

---

## Formato do Takeout Suportado

O Instagram exporta o Takeout em **JSON** e/ou **HTML**. O parser detecta
automaticamente e trata os dois:

| Formato | Arquivos | Timestamp |
|---------|----------|-----------|
| JSON | `followers_1.json`, `following.json` | ✅ presente |
| HTML | `followers_1.html`, `following.html` | ❌ ausente |

Arquivos **ignorados** pelo parser (fora do escopo):
`close_friends.json`, `blocked_profiles.json`, `pending_follow_requests.json`,
`recent_follow_requests.json`, `restricted_profiles.json`,
`recently_unfollowed_profiles.json`, `following_hashtags.json`.

---

## Segurança e LGPD

- ❌ Nunca solicitamos nem armazenamos a senha do Instagram.
- ✅ Uploads processados e **apagados** após parsing (padrão).
- ✅ Isolamento estrito entre clientes (testado).
- ✅ Downloads e demais rotas de pedidos exigem autenticação (Bearer).
- ✅ Retenção configurável (`RETENTION_DAYS`, padrão 30 dias).
- ✅ Neutralização de fórmulas no CSV/XLSX (anti-injeção).

**Contas e sessões**
- ✅ Hash de senha com Argon2id.
- ✅ Limite de tentativas de login (rate limit via Redis).
- ✅ Confirmação de e-mail obrigatória para entrar (link válido por 24 h) e exige a senha do cadastro, o que impede o pré-sequestro de conta por quem cadastrou o e-mail alheio.
- ✅ Link de redefinição de senha válido por 30 min e de uso único.
- ✅ Trocar a senha derruba as sessões abertas.
- ✅ Cadastro, reenvio e recuperação não revelam se o e-mail está cadastrado (mesma resposta; quem já tem conta recebe um aviso por e-mail).
- ✅ Teto de 6 e-mails por hora por destinatário em cada fluxo, independente do IP.

**API e uploads**
- ✅ Cabeçalhos de segurança na API e no frontend (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy: no-referrer`; HSTS com `APP_ENV=production`).
- ✅ `/docs`, `/redoc` e `/openapi.json` desativados em produção (`APP_ENV=production` ou `ENABLE_DOCS=0`).
- ✅ Proteção contra ZIP bomb: limite de entradas, tamanho por arquivo e total descompactado, taxa de compressão e leitura limitada.
- ✅ Corpos grandes rejeitados pelo `Content-Length` (413) antes de serem gravados em disco.
- ✅ Limite de envios por hora e de pedidos guardados por usuário (`UPLOADS_PER_HOUR`, `MAX_ORDERS_PER_USER`).

**Pendente para produção**
- ⚠️ Token de sessão em cookie `httpOnly` (hoje fica no `localStorage`).
- ⚠️ `--proxy-headers` no uvicorn, para o rate limit enxergar o IP real atrás de proxy.
- ⚠️ Limite de corpo no proxy (`client_max_body_size`): corpos *chunked* não trazem `Content-Length`.
- ⚠️ Senha no Redis (`REDIS_PASSWORD` + `REDIS_URL`), versões fixas das dependências e frontend com build de produção.
- ⚠️ Cadastro pendente pode ser sobrescrito por terceiros (só atrapalha, não dá acesso); o desenho definitivo guarda o pendente em tabela própria.

> O envio de uma exportação pelo cliente **não concede automaticamente**
> permissão para uso posterior dos dados de terceiros. Base legal e
> salvaguardas devem ser avaliadas para cada finalidade.

---

## Roadmap

- [x] Parser JSON + HTML
- [x] Autenticação e isolamento
- [x] Fila assíncrona
- [x] Exportação CSV/XLSX
- [x] Confirmação de e-mail e recuperação de senha
- [x] Frontend: login, cadastro e recuperação de senha
- [ ] **Integração com provedor de enriquecimento (Apify ou similar)**
- [ ] Frontend: upload do ZIP, lista de pedidos e downloads
- [ ] Migrações com Alembic (hoje `create_all` + `ALTER` pontual)
- [ ] Provedor SMTP real e domínio (SPF/DKIM) para produção
- [ ] Sessão em cookie `httpOnly`, logout e revogação de sessão
- [ ] Cadastro pendente em tabela própria
- [ ] Página reserva (backup de perfil)
- [ ] CRM leve
- [ ] Agentes de IA para classificação de bios

---

## Como Contribuir

1. Crie uma branch: `git checkout -b feat/nome-da-feature`
2. Commits pequenos e descritivos.
3. Rode os testes antes de abrir PR: `docker compose exec api pytest`
4. Abra PR explicando **o quê** e **por quê**.

---

## Referências

- Produto de referência: <https://seguenoinsta.nucleodigital.cc/>
- Google Takeout: <https://takeout.google.com/>
- Instagram Help Center: <https://help.instagram.com/> (buscar "Baixar suas informações")
- ANPD: <https://www.gov.br/anpd/pt-br>
- Meta for Developers: <https://developers.facebook.com/terms/>
