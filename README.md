# BKP — SaaS de Backup Enriquecido do Instagram

[![CI](https://github.com/Ian-Mendes/bkp/actions/workflows/ci.yml/badge.svg)](https://github.com/Ian-Mendes/bkp/actions/workflows/ci.yml)

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
| Convite de acesso (backoffice, sem e-mail) | ✅ Funcionando |
| Frontend: login e aceite de convite | ✅ Funcionando |
| Isolamento entre clientes | ✅ Testado |
| Retenção e exclusão (LGPD) | ✅ Implementado |
| Sessão em cookie httpOnly + refresh | ✅ Implementado |
| Fila assíncrona (Celery + Redis) | ⏳ Adiada — e-mail e enriquecimento rodam no processo por ora; a fila volta com o provider real |
| Exportação CSV/XLSX | ✅ Implementado |
| **Enriquecimento (provider real)** | ⏳ **Pendente** — usando `NullProvider` |
| Frontend: upload do ZIP | ✅ Implementado no painel |
| Frontend: lista de pedidos e downloads | ⏳ Pendente |

---

## Stack

**Backend**
- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy + PostgreSQL 16
- APScheduler (retenção)
- PyJWT + argon2-cffi
- openpyxl (XLSX)
- httpx, python-multipart, pydantic-settings, email-validator
- pytest (50 testes)

**Infraestrutura**
- Docker + Docker Compose
- Armazenamento privado de arquivos (volume local; S3 na produção)
- Sem e-mail: convites de acesso gerados por comando de backoffice
- Caddy (gateway de produção, perfil `prod`; em dev o Vite serve o frontend)

**Frontend**
- Vite 5 + React 18 (react-router-dom, JavaScript)

---

## Estrutura do Projeto

```
bkp/
├── README.md
├── CONTRIBUTING.md
├── docker-compose.yml          # db, redis, api, worker (+ perfil prod com Caddy)
├── docker-compose.override.yml # dev: sobe o frontend (Vite) com hot reload
├── .env.example
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/
├── frontend/
│   ├── Dockerfile              # multi-stage: deps → dev → build → caddy
│   ├── Caddyfile               # gateway de produção (estáticos + proxy /api)
│   ├── vite.config.js          # proxy de /api em dev
│   ├── index.html
│   └── src/
│       ├── main.jsx            # entrypoint
│       ├── App.jsx             # rotas (react-router)
│       ├── index.css
│       ├── lib/api.js          # cliente da API + token
│       └── pages/              # Home, Login, VerifyEmail, ForgotPassword,
│                               # ResetPassword, Dashboard (provisória)
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── app/
    │   ├── main.py             # API FastAPI + agendador de retenção (APScheduler)
    │   ├── worker.py           # stub comentado (fila reintroduzida depois)
    │   ├── importer.py         # Parser do Takeout (JSON + HTML) + ZIP bomb
    │   ├── services.py         # Regras de negócio (enriquecimento síncrono)
    │   ├── exporter.py         # CSV/XLSX + anti-injeção
    │   ├── models.py           # SQLAlchemy
    │   ├── auth.py             # Convite (aceite), login, sessão e revogação
    │   ├── invite.py           # Comando de backoffice: gera links de convite
    │   ├── security.py         # Argon2 + JWT (sessão e refresh) + hash de convite
    │   ├── rate.py             # Rate limiting (em memória)
    │   └── providers/          # Fontes de enriquecimento
    │       ├── base.py
    │       ├── null_provider.py
    │       └── (futuro) apify_provider.py
    ├── tests/                  # pytest (API, auth, e-mail, segurança, importer)
    └── tools/                  # Scripts de análise e debug (count_files, dates)
```

---

## Como Rodar (Docker) — Passo a Passo

### Pré-requisitos

- Git
- Docker e Docker Compose v2 (o comando é `docker compose`, sem hífen)
- `openssl` (para gerar senhas; já vem no Linux e no macOS)

Confira:

```bash
git --version
docker --version
docker compose version
```

### 1. Clonar

```bash
git clone https://github.com/Ian-Mendes/bkp.git
cd bkp
```

> O Docker Compose usa o **nome da pasta** como prefixo dos containers e volumes
> (pasta `bkp` → `bkp-api-1`, `bkp_pgdata`; pasta `saas-backup` → `saas-backup-api-1`).

### 2. Permissão para usar o Docker (só Linux)

Se `docker ps` responder `permission denied while trying to connect to the docker API`,
seu usuário não está no grupo `docker`. Duas saídas:

**a) Usar `sudo` em todo comando:** `sudo docker compose ...`

**b) Adicionar o usuário ao grupo `docker` (uma vez só):**

```bash
sudo usermod -aG docker $USER
newgrp docker        # vale só para este terminal; para todos, faça logout/login
docker ps            # deve funcionar sem sudo
```

> ⚠️ Quem acessa o socket do Docker tem, na prática, poder equivalente a root na máquina.
> Em máquina pessoal de desenvolvimento isso costuma ser aceitável. Se quiser evitar,
> use o [Docker rootless](https://docs.docker.com/engine/security/rootless/).
>
> Não use `chown` no `/var/run/docker.sock`: o Docker recria o socket ao reiniciar
> e a permissão se perde.
>
> Se usou `sudo` com `git clone` ou `git pull`, devolva o dono dos arquivos:
> `sudo chown -R $USER:$USER .` e use `git` sem `sudo` daqui para frente.

### 3. Configurar o `.env` (passo mais importante)

O `.env.example` traz três campos **vazios ou de exemplo** que você precisa preencher
**antes do primeiro `docker compose up`**:

| Variável | O que é | Regra |
|----------|---------|-------|
| `POSTGRES_PASSWORD` | Senha do banco | Não pode ficar vazia |
| `DATABASE_URL` | URL de conexão da API ao banco | A senha dentro dela deve ser **idêntica** à `POSTGRES_PASSWORD` (troque o `SENHA`) |
| `JWT_SECRET` | Assina os tokens de login | 32+ caracteres |

**Jeito rápido (Linux/macOS)**, gera tudo aleatório e grava nas linhas certas:

```bash
cp .env.example .env

PW=$(openssl rand -hex 16)
JWT=$(openssl rand -hex 32)

sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$PW/" .env
sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+psycopg://app:$PW@db:5432/backup#" .env
sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$JWT/" .env
```

No macOS, troque `sed -i` por `sed -i ''`. No Windows (PowerShell), use
`Copy-Item .env.example .env` e edite os três campos à mão.

**Confira o resultado:**

```bash
grep -nE 'POSTGRES_PASSWORD|DATABASE_URL|JWT_SECRET' .env
```

Deve aparecer a mesma senha em `POSTGRES_PASSWORD` e dentro de `DATABASE_URL`,
nenhum `SENHA` sobrando e um `JWT_SECRET` com 64 caracteres. Cada variável deve
aparecer **uma vez só** (linha duplicada vazia sobrescreve a preenchida).

Regras para a senha do banco: use só letras e números. Caracteres como `@ / : #`
quebram a `DATABASE_URL`.

### 4. Subir

```bash
docker compose up -d --build
```

O primeiro build leva alguns minutos (baixa imagens e instala dependências).
O `-d` roda em segundo plano: pode fechar o terminal que os containers continuam de pé.

> Atalho: `make dev` equivale a `docker compose up -d --build` (e cria o `.env` se faltar).

### 5. Validar que está tudo certo

Rode os comandos abaixo, na ordem. Cada um tem o resultado esperado.

| # | Comando | Resultado esperado |
|---|---------|--------------------|
| 1 | `docker compose ps` | 5 serviços `Up` (`api`, `db`, `redis`, `worker`, `frontend`); `db` com `(healthy)` |
| 2 | `docker compose logs api --tail 20` | Termina com `Application startup complete` e **sem** traceback |
| 3 | `curl -i http://localhost:8000/health` | `HTTP/1.1 200 OK` |
| 4 | `docker compose exec api sh -c 'echo ${#JWT_SECRET}'` | `64` (ou pelo menos `32`) |
| 5 | `docker compose exec db psql -U app -d backup -c '\dt'` | Lista as tabelas (`users`, `invites`, `orders`, `profiles`, `takeout_entries`), provando que o banco aceita a senha |
| 6 | `docker compose exec api pytest` | Todos os testes passam |
| 7 | Abrir http://localhost:3000 | Tela de login do frontend |

> ⚠️ **O `pytest` passar não prova que o banco está conectado.** Os testes passam mesmo
> quando a API não consegue autenticar no Postgres. Sempre confirme também os passos
> 2, 3 e 5.

Serviços e portas (todos só em localhost):

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API (Swagger em `/docs`, só em desenvolvimento) | http://localhost:8000 |


### 6. Criar o primeiro convite e ativar a conta

1. Gere um convite pelo comando de backoffice:

   ```bash
   docker compose exec api python -m app.invite voce@exemplo.com
   ```

2. O comando imprime um link de uso único (ex.: `http://localhost:3000/invite/<token>`).
   Envie esse link para a pessoa, fora da aplicação.
3. Ao abrir o link, a pessoa define a senha e já entra no painel (sem verificação por e-mail).

---

## Solução de Problemas

Procure pelo sintoma. Quando não souber a causa, o primeiro passo é sempre
`docker compose ps` e depois `docker compose logs <serviço> --tail 50`.

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `permission denied ... docker.sock` | Usuário fora do grupo `docker` | Use `sudo` ou veja o passo 2 |
| `db` sai com código 1; `dependency failed to start`; `service "api" is not running` | `POSTGRES_PASSWORD` vazio. O log do `db` diz `Database is uninitialized and superuser password is not specified` | Preencha o `.env` (passo 3), depois `docker compose down -v && docker compose up -d` |
| `curl` responde `Recv failure: Conexão fechada pela outra ponta`; `api` aparece `Up` | O app falhou ao iniciar e o uvicorn ficou de pé sem aplicação. Veja o traceback em `docker compose logs api` | Corrija o erro apontado no log (as duas linhas abaixo são as mais comuns) |
| `RuntimeError: JWT_SECRET precisa ter pelo menos 32 caracteres` | `JWT_SECRET` vazio ou curto | Preencha com `openssl rand -hex 32` e rode `docker compose up -d --force-recreate api` |
| `password authentication failed for user "app"` | Senha da `DATABASE_URL` diferente da gravada no volume do Postgres | Deixe as duas senhas iguais no `.env` e recrie o banco: `docker compose down -v && docker compose up -d` (**apaga os dados do banco**) |
| `Bind for 127.0.0.1:8025 failed: port is already allocated` (ou 3000/8000) | Outra coisa usa a porta, quase sempre containers de outra cópia do projeto | `docker ps --format 'table {{.Names}}\t{{.Ports}}'` para achar o dono; remova com `docker rm -f NOME`, ou na outra pasta rode `docker compose down`. Se não for Docker: `sudo ss -ltnp \| grep 8025` |
| Mudei o `.env` e nada mudou | `restart` não relê o `.env` | `docker compose up -d --force-recreate` |
| Mudei `requirements.txt` ou `package.json` | Imagem precisa ser reconstruída | `docker compose up -d --build` |
| Erro de `column ... does not exist` após atualizar | Não há migrações ainda (`create_all`); o schema evolui (ex.: `profiles` virou tabela global e `takeout_entries` é nova) e o banco antigo não acompanha | Em desenvolvimento: `docker compose down -v && docker compose up -d` (apaga os dados) |

> **Por que o banco "ignora" a senha nova?** O Postgres só lê `POSTGRES_PASSWORD`
> na **primeira** inicialização do volume. Depois disso, a senha fica gravada no
> volume e mudar o `.env` não a altera. Por isso, ao trocar a senha, é preciso
> recriar o volume com `docker compose down -v`.

---

## Atualizar o Projeto (depois de um `git pull`)

```bash
git pull                      # sem sudo
git diff HEAD@{1} -- .env.example   # apareceu variável nova? copie para o seu .env
docker compose up -d --build
docker compose ps
docker compose logs api --tail 20
```

- O seu `.env` **não** é atualizado pelo `git pull` (ele não é versionado; só o
  `.env.example` é). Compare os dois e acrescente o que faltar.
- Se o `git pull` recusar por alterações locais: `git stash`, `git pull`, `git stash pop`.
- Depois de atualizar, repita a validação do passo 5.

---

## Comandos do Dia a Dia

```bash
docker compose ps                 # estado dos serviços
docker compose logs -f api        # acompanhar logs de um serviço
docker compose restart api        # reiniciar um serviço
docker compose down               # parar tudo (mantém os dados)
docker compose up -d              # subir de novo
```

> ⚠️ `docker compose down -v` **apaga os volumes** (banco, uploads). Use só quando
> quiser recomeçar do zero.

### Deixar rodando de forma permanente

Para os serviços voltarem sozinhos depois de reiniciar a máquina ou de uma queda,
adicione em cada serviço do `docker-compose.yml`:

```yaml
restart: unless-stopped
```

E garanta que o Docker inicia com o sistema (Linux): `sudo systemctl enable docker`.

---

## Makefile

Atalhos para os comandos mais comuns (tudo em container; nunca `pytest`/`pip`/`npm` na máquina):

| Comando | Efeito |
|---------|--------|
| `make setup` | Cria o `.env` a partir do `.env.example` (não sobrescreve) e avisa se `JWT_SECRET` está curto |
| `make dev` | `docker compose up -d --build` (cria o `.env` se faltar) |
| `make build` | `docker compose build` |
| `make test` | `docker compose exec api pytest` |
| `make prod` | `docker compose -f docker-compose.yml --profile prod up -d --build` (gateway Caddy) |
| `make prod-down` | `docker compose -f docker-compose.yml --profile prod down` |
| `make down` | `docker compose down` |
| `make reset` | `docker compose down -v && docker compose up -d --build` |
| `make logs` | `docker compose logs -f` |

---

## Resetar os Dados

```bash
# Apagar tudo (banco e uploads)
docker compose down -v && docker compose up -d

# Só usuários, pedidos e perfis (e as relações do takeout)
docker compose exec db psql -U app -d backup -c "TRUNCATE users, orders, profiles, takeout_entries RESTART IDENTITY CASCADE;"

# Zerar limites de tentativas (rate limit): o contador é em memória,
# então basta reiniciar a API
docker compose restart api
```

---

## Testar o convite de acesso

Não há e-mail: o acesso é por convite gerado no backoffice.

```bash
# Gera um link de uso único (válido por INVITE_DAYS, padrão 7 dias)
docker compose exec api python -m app.invite voce@exemplo.com

# Valida o convite antes de mostrar o formulário de senha
curl -i http://localhost:8000/auth/invite/<token>
```

**Convidar vários usuários (lote):** leia de um arquivo com um e-mail por linha
(linhas em branco são ignoradas). O `-T` desativa o TTY para o stdin funcionar.

```bash
# Imprime um link por e-mail
docker compose exec -T api python -m app.invite < emails.txt

# Salvar os links em um arquivo
docker compose exec -T api python -m app.invite < emails.txt > convites.txt
```

- O link é de uso único e expira em 7 dias; re-convidar o mesmo e-mail regenera o link (o antigo morre).
- E-mail que já tem conta ativa é ignorado (imprime `já tem conta ativa — ignorado`).
- Definir a senha (`/auth/accept-invite`) já autentica: o usuário cai direto no painel.

---

## Variáveis de Ambiente (`.env`)

```env
# Banco (a senha da DATABASE_URL deve ser igual à POSTGRES_PASSWORD)
POSTGRES_PASSWORD=troque_esta_senha
DATABASE_URL=postgresql+psycopg://app:troque_esta_senha@db:5432/backup

# Fila (reservado; reintroduzir ao reativar Celery/Redis com o provider real)
# REDIS_URL=redis://redis:6379/0
# REDIS_PASSWORD=

# Segurança (mínimo 32 caracteres)
JWT_SECRET=troque_por_uma_string_aleatoria_com_32_mais_caracteres
TOKEN_MINUTES=60                     # duração da sessão (padrão 60; opcional)
REFRESH_DAYS=30                      # validade do refresh token (cookie httpOnly); padrão 30

# Uploads
MAX_UPLOAD_MB=200
KEEP_UPLOADS=0

# Retenção (dias)
RETENTION_DAYS=30

# Provider de enriquecimento
PROVIDER=null          # null | apify
APIFY_TOKEN=           # preencher quando implementar
APIFY_ACTOR_ID=apify/instagram-profile-scraper

# Convite de acesso (base do link gerado pelo backoffice; sem e-mail)
FRONTEND_URL=http://localhost:3000
INVITE_DAYS=7                        # validade do convite em dias

# Segurança / produção
APP_ENV=development        # production: ativa HSTS e desativa /docs (a menos que ENABLE_DOCS=1)
ENABLE_DOCS=1              # 0 desativa /docs, /redoc e /openapi.json
UPLOADS_PER_HOUR=10        # envios de ZIP por usuário por hora
MAX_ORDERS_PER_USER=20     # pedidos guardados por usuário
```

Os valores de segurança têm padrão no código; só precisam estar no `.env` para mudar.

O frontend chama a API pela mesma origem (`/api`), encaminhada pelo proxy
(Vite em dev, Caddy em produção) — sem variável a configurar; ver `frontend/.env.example`.

**Nunca comite o `.env` real** (confira se ele está no `.gitignore`). Use `.env.example` como modelo
e gere um `JWT_SECRET` e uma senha de banco diferentes para cada ambiente, principalmente produção.

---

## Fluxo de Uso da API

```bash
# 1. Criar convite (backoffice; imprime o link de uso único)
docker compose exec api python -m app.invite voce@exemplo.com

# 2. Aceitar o convite definindo a senha (já autentica)
curl -X POST http://localhost:8000/auth/accept-invite \
  -H "Content-Type: application/json" \
  -d '{"token":"...","password":"senha-bem-longa-123"}'
TOKEN="..."

# 3. (Opcional) Login para renovar/recuperar a sessão
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@exemplo.com","password":"senha-bem-longa-123"}'
TOKEN="..."

> O login também seta um cookie `httpOnly` (`bkp_session`) + `bkp_refresh`. No
> navegador, o cookie é o mecanismo principal; o `access_token` no corpo é
> fallback para clientes que ainda usam `Authorization: Bearer`.

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

# 6b. Prévia paginada dos perfis (opcional: limit, offset, tipo, q)
curl "http://localhost:8000/orders/$ORDER_ID/profiles?limit=50&offset=0&tipo=ambos" \
  -H "Authorization: Bearer $TOKEN"

# 7. Baixar relatório
curl http://localhost:8000/orders/$ORDER_ID/report \
  -H "Authorization: Bearer $TOKEN"

# 8. Baixar planilhas
curl -o backup.csv  http://localhost:8000/orders/$ORDER_ID/export.csv  -H "Authorization: Bearer $TOKEN"
curl -o backup.xlsx http://localhost:8000/orders/$ORDER_ID/export.xlsx -H "Authorization: Bearer $TOKEN"
```

Códigos úteis: `401` token inválido ou senha errada, `413` corpo grande demais,
`429` limite de tentativas, `409` limite de pedidos guardados por usuário.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/auth/accept-invite` | Aceita o convite (define senha) e autentica |
| GET | `/auth/invite/{token}` | Valida o convite e devolve o e-mail |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Dados do usuário |
| POST | `/auth/refresh` | Renova o access token a partir do refresh cookie |
| POST | `/auth/logout` | Invalida os cookies de sessão e refresh |
| POST | `/orders` | Upload do ZIP |
| GET | `/orders/upload-config` | Limite de upload em bytes (autenticado) |
| GET | `/orders` | Lista pedidos |
| GET | `/orders/{id}` | Detalhe do pedido |
| GET | `/orders/{id}/profiles` | Prévia paginada dos perfis (`limit`/`offset`/`tipo`/`q`) |
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
- ✅ Retenção configurável (`RETENTION_DAYS`, padrão 30 dias) — apaga pedidos e a relação seguidor/seguindo; o cache de perfis enriquecidos (dados públicos) persiste para reuso.
- ✅ Neutralização de fórmulas no CSV/XLSX (anti-injeção).

**Contas e sessões**
- ✅ Hash de senha com Argon2id.
- ✅ Limite de tentativas de login (rate limit em memória).
- ✅ Acesso só por convite de uso único (token hasheado, expira em `INVITE_DAYS`); sem auto-cadastro.
- ✅ `accept-invite` com rate limit por IP; inválido/expirado/já usado devolve a mesma resposta (sem vazar qual).
- ✅ Trocar a senha (ou fazer logout) derruba as sessões abertas via `token_version`.
- ✅ Sessão em cookie httpOnly (`bkp_session`) com refresh token (`bkp_refresh`); `token_version` permite revogação em massa.

**API e uploads**
- ✅ Cabeçalhos de segurança na API e no frontend (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy: no-referrer`; HSTS com `APP_ENV=production`).
- ✅ `/docs`, `/redoc` e `/openapi.json` desativados em produção (`APP_ENV=production` ou `ENABLE_DOCS=0`).
- ✅ Proteção contra ZIP bomb: limite de entradas, tamanho por arquivo e total descompactado, taxa de compressão e leitura limitada.
- ✅ Corpos grandes rejeitados pelo `Content-Length` (413) antes de serem gravados em disco.
- ✅ Limite de envios por hora e de pedidos guardados por usuário (`UPLOADS_PER_HOUR`, `MAX_ORDERS_PER_USER`).

**Pendente para produção**
- ⚠️ `--proxy-headers` no uvicorn, para o rate limit enxergar o IP real atrás de proxy.
- ⚠️ Limite de corpo no proxy (`request_body max_size` no `Caddyfile`): corpos *chunked* não trazem `Content-Length`.
- ⚠️ Rate limit em memória e agendador de retenção são single-instance: mover para Redis/fila ao escalar para várias réplicas.
- ⚠️ Versões fixas das dependências (`requirements.txt` sem pin).

> O envio de uma exportação pelo cliente **não concede automaticamente**
> permissão para uso posterior dos dados de terceiros. Base legal e
> salvaguardas devem ser avaliadas para cada finalidade.

---

## Deploy e Produção

Provedor definido: **Vultr (VPS)**. Roteiro passo a passo com comandos exatos e
critério de "pronto" em cada etapa. Para agentes de IA: siga a ordem — cada passo
lista o que falta e como validar.

### Topologia

- **Um VPS (Cloud Compute)** rodando o Docker Compose com `db` + `redis` + `api`
  + `worker` + `web` (Caddy). Réplica única por causa do rate limit em memória e
  do agendador de retenção (APScheduler) — não escale ainda.
- **Uploads**: volume local do Docker no VPS por ora. Migração futura para o
  **Vultr Object Storage** (S3-compatível); as variáveis `S3_*` no `.env.example`
  já reservam isso, mas **ainda não são usadas no código**.
- **Domínio + HTTPS**: o DNS aponta para o IP do VPS e o Caddy emite o
  certificado automaticamente (Let's Encrypt).

### O que você precisa em mãos (antes de começar)

- [ ] Conta Vultr (com cartão) e chave pública SSH
- [ ] Domínio (ex.: `backup.exemplo.com`) com acesso ao DNS
- [ ] Conta GitHub com acesso ao repositório (imagens no GHCR e CD)
- [ ] Conta Apify (para o enriquecimento real)
- [ ] Um PAT do GitHub com `read:packages` (ou pacote GHCR público)

### 1. Provisionar o VPS na Vultr

1. Acesse my.vultr.com → **Products → Deploy New Server**.
2. Escolha:
   - **Type**: Cloud Compute – Regular Performance (ou High Frequency)
   - **Image**: Ubuntu 24.04 LTS x64
   - **Size**: mínimo 2 GB / 1 vCPU; **recomendado 4 GB** (API + worker Celery +
     Postgres + Redis na mesma máquina)
   - **Region**: a mais próxima dos usuários
   - **SSH Keys**: selecione sua chave pública
3. **Firewall** (Products → Network → Firewalls): crie um grupo liberando
   **22 (SSH)**, **80 (HTTP)** e **443 (HTTPS)** e associe ao servidor. **Não**
   abra 8000, 5432 (Postgres) nem 6379 (Redis) — esses ficam só na rede interna
   do Docker Compose.

✅ **Pronto:** você recebeu um IP público e consegue `ssh root@<IP>`.

### 2. Preparar o VPS (uma única vez)

```bash
ssh root@<IP>

# Docker + plugin Compose v2.26+ (o docker-compose.prod.yml usa !reset/!override)
apt-get update && apt-get install -y ca-certificates curl
curl -fsSL https://get.docker.com | sh
docker compose version          # deve ser >= 2.26

# Diretório do projeto
mkdir -p /opt/bkp

# Autenticar no GHCR (leitura das imagens). PAT com scope read:packages,
# ou torne o pacote público no GitHub.
docker login ghcr.io -u <SEU_USUARIO_GITHUB>
```

✅ **Pronto:** `docker compose version` ≥ 2.26 e `docker login ghcr.io` sem erro.

### 3. Criar a chave da Apify

1. Crie a conta em console.apify.com.
2. **Settings → Integrations → API token** → copie o token.
3. O actor padrão já vem no `.env.example`
   (`APIFY_ACTOR_ID=apify/instagram-profile-scraper`). Confirme no console que o
   actor existe e está acessível à sua conta.

Guarde o token — ele vai em `APIFY_TOKEN` no `.env` (passo 5).

✅ **Pronto:** token copiado.

### 4. Apontar o DNS

Crie um registro `A` (ou `CNAME`) no seu DNS apontando o domínio para o IP
público do VPS:

```bash
dig +short backup.exemplo.com   # deve retornar o IP do VPS
```

✅ **Pronto:** o domínio resolve para o IP (a propagação pode levar alguns minutos).

### 5. Criar o `.env` de produção

No servidor, em `/opt/bkp`, crie o `.env` a partir do `.env.example` e preencha
**todos** os campos abaixo. Gere segredos novos — nunca reuse os de dev.

| Variável | Valor em produção | Como obter |
|---|---|---|
| `POSTGRES_PASSWORD` | senha aleatória | `openssl rand -hex 16` |
| `DATABASE_URL` | `postgresql+psycopg://app:<MESMA_SENHA>@db:5432/backup` | senha **idêntica** à `POSTGRES_PASSWORD` |
| `REDIS_URL` | `redis://redis:6379/0` | padrão |
| `REDIS_PASSWORD` | vazio | opcional (o Redis não publica porta) |
| `JWT_SECRET` | ≥ 32 chars | `openssl rand -hex 32` |
| `APP_ENV` | `production` | fixo (ativa HSTS e desativa `/docs`) |
| `ENABLE_DOCS` | `0` | fixo |
| `FRONTEND_URL` | `https://backup.exemplo.com` | seu domínio (base dos links de convite) |
| `PROVIDER` | `apify` | para enriquecimento real (`null` desativa) |
| `APIFY_TOKEN` | token da Apify | passo 3 |
| `APIFY_ACTOR_ID` | `apify/instagram-profile-scraper` | default |

Atalho (substitua o domínio e o token):

```bash
cd /opt/bkp
cp .env.example .env
PW=$(openssl rand -hex 16)
JWT=$(openssl rand -hex 32)
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$PW/" .env
sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+psycopg://app:$PW@db:5432/backup#" .env
sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$JWT/" .env
sed -i "s/^APP_ENV=.*/APP_ENV=production/" .env
sed -i "s/^ENABLE_DOCS=.*/ENABLE_DOCS=0/" .env
sed -i "s/^FRONTEND_URL=.*/FRONTEND_URL=https://backup.exemplo.com/" .env
sed -i "s/^PROVIDER=.*/PROVIDER=apify/" .env
sed -i "s/^APIFY_TOKEN=.*/APIFY_TOKEN=SEU_TOKEN_APIFY/" .env
grep -nE 'POSTGRES_PASSWORD|DATABASE_URL|JWT_SECRET|APP_ENV|ENABLE_DOCS|FRONTEND_URL|PROVIDER|APIFY_TOKEN' .env
```

Notas:

- A senha dentro de `DATABASE_URL` precisa ser **idêntica** à `POSTGRES_PASSWORD`
  (o Postgres só lê a senha na primeira criação do volume).
- Se definir `REDIS_PASSWORD`, inclua-a na URL:
  `redis://:SENHA@redis:6379/0`. Para uma réplica única pode deixar ambos vazios.
- As variáveis `S3_*` continuam **comentadas** (não usadas no código).

✅ **Pronto:** o `grep` mostra as variáveis preenchidas, sem `SENHA`/`SEU_TOKEN` sobrando.

### 6. Ajustar o Caddyfile para o domínio

O domínio vai **embutido na imagem `web`** (o `frontend/Caddyfile` é copiado no
build). Edite `frontend/Caddyfile` e troque `:80` por `backup.exemplo.com`:

```caddyfile
backup.exemplo.com {
    root * /srv

    handle_path /api/* {
        reverse_proxy api:8000
    }

    handle {
        # ... headers e fallback SPA (mantenha o restante como está)
    }
}
```

> Sem o domínio (mantendo `:80`), o Caddy serve HTTP puro e o cookie de sessão
> (`secure=True` com `APP_ENV=production`) **não funciona** no navegador.

Se usar as imagens do GHCR (passo 8, opção A), **faça commit e push** para o
`release.yml` reconstruir a `web` com o domínio. No build local (opção B), o
build usa o Caddyfile do repositório clonado.

✅ **Pronto:** Caddyfile apontando para o domínio (e, no fluxo GHCR, commit enviado).

### 7. Aplicar as migrações do banco (Alembic)

O schema é versionado por Alembic e **não** é criado no boot (não há
`create_all`). Depois de subir (passo 8), rode:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod exec api alembic upgrade head
```

Rode de novo sempre que houver revisão nova em `backend/alembic/versions/`.

✅ **Pronto:** `... exec db psql -U app -d backup -c '\dt'` lista `users`, `invites`,
`orders`, `profiles`, `takeout_entries` e `alembic_version`.

### 8. Subir o ambiente

**Opção A — imagens do GHCR (recomendada; é o que o CD usa):**

```bash
cd /opt/bkp
export IMAGE_TAG=main
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d
```

**Opção B — build local no servidor (sem depender do GHCR):**

```bash
cd /opt/bkp
docker compose -f docker-compose.yml --profile prod up -d --build   # ou `make prod`
```

Em seguida rode o passo 7 (migrações) e valide (passo 9).

> `--profile prod` ativa o serviço `web` (Caddy, gateway único em `:80`/`:443`).
> Em produção `api` e `redis` **não publicam porta**.

### 9. Validar e criar o primeiro convite

```bash
cd /opt/bkp
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod"

# 1. Serviços de pé (api, db, redis, worker e web)
$COMPOSE ps

# 2. Healthcheck (a API não publica porta em prod; consulta por dentro do container)
$COMPOSE exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# 3. HTTPS: abrir https://backup.exemplo.com no navegador (cadeado válido)

# 4. Criar o primeiro convite de acesso (imprime o link de uso único)
$COMPOSE exec api python -m app.invite voce@exemplo.com
```

✅ **Pronto:** `/health` responde `200`, o site carrega em HTTPS e o convite abre a
tela de definir senha.

### 10. Backup do banco (agendar)

```bash
# pg_dump comprimido; apaga backups com +30 dias (mesma janela da retenção LGPD)
scripts/backup.sh 30 /opt/bkp/backups
```

Agende no cron do servidor (ex.: diário):

```cron
0 3 * * * cd /opt/bkp && ./scripts/backup.sh 30 /opt/bkp/backups >> /var/log/bkp-backup.log 2>&1
```

Para os serviços voltarem sozinhos após reiniciar a máquina, adicione
`restart: unless-stopped` a cada serviço (ou gerencie com `systemd`) e garanta
`sudo systemctl enable docker`.

### Deploy contínuo (CD via GitHub Actions) — opcional

O workflow `deploy.yml` faz o deploy por SSH, puxando as imagens do GHCR. Roda
automaticamente quando o `release.yml` termina na `main` e também aceita
execução manual ("Actions" → "Deploy" → "Run workflow"), com um campo `ref` para
escolher a tag — use o `sha` de um commit anterior para **rollback**.

**Secrets do GitHub** (Settings → Secrets and variables → Actions):

| Secret | O que é |
|--------|---------|
| `DEPLOY_HOST` | IP/domínio do VPS |
| `DEPLOY_USER` | usuário SSH (ex.: `root`) |
| `SSH_PRIVATE_KEY` | chave privada SSH (a pública fica em `~/.ssh/authorized_keys` do VPS) |
| `DEPLOY_PATH` | diretório do projeto no servidor (ex.: `/opt/bkp`) |

Enquanto esses secrets não existirem, o job fica **inerte** (o passo é pulado).
A preparação única no VPS (passos 2, 5 e 6) deve ser feita antes de habilitar o CD.

**Validação e rollback:**

```bash
# healthcheck (a API não publica porta em prod; consulta por dentro do container)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# rollback: implante a tag do commit anterior
IMAGE_TAG=<sha-anterior> docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d
```

O `docker-compose.prod.yml` usa as imagens publicadas (`ghcr.io/ian-mendes/bkp/*`)
e remove o `--reload`/bind mount de dev. Requer Docker Compose v2.26+.

### Pendências de produção (não esquecer)

- ⚠️ **Migrações no CD**: o `deploy.yml` só faz `pull` + `up`; **não** roda
  `alembic upgrade head`. Em schema novo, rode o passo 7 manualmente após o
  deploy (ou automatize o passo no workflow).
- ⚠️ **Uma réplica só (por ora)**: rate limit (`rate.py`) e agendador de retenção
  (APScheduler) são em memória/single-instance — não escale para mais de uma
  réplica até a fila Redis voltar (Issue #11).
- ⚠️ `--proxy-headers` no uvicorn (para o rate limit ver o IP real atrás do
  proxy) e limite de corpo no Caddy ainda pendentes — ver "Segurança e LGPD".

---

## Roadmap

- [x] Parser JSON + HTML
- [x] Autenticação e isolamento
- [x] Exportação CSV/XLSX
- [x] Convite de acesso (backoffice, sem e-mail)
- [x] Frontend: login e aceite de convite
- [x] **Integração com provedor de enriquecimento (Apify)** — implementado, inativo por padrão (`PROVIDER=null`); ativação com token (#22) e escala com fila (#14)
- [x] Fila assíncrona (Celery + Redis)
- [x] Frontend: upload do ZIP
- [x] Frontend: lista de pedidos e downloads
- [x] Migrações com Alembic (hoje `create_all` + `ALTER` pontual) — #26 (antes do staging)
- [x] CI (GitHub Actions) e publicação de imagens (GHCR)
- [ ] Deploy em staging/produção (provedor: Vultr; aguardando provisionamento do servidor)
- [x] Sessão em cookie `httpOnly`, logout e revogação de sessão
- [x] Cadastro pendente em tabela própria (tabela `invites`)
- [ ] Página reserva (backup de perfil)
- [ ] CRM leve
- [ ] Agentes de IA para classificação de bios
- [ ] Definir a `LICENSE` (hoje o repositório não declara nenhuma)

---

## Como Contribuir

Veja `CONTRIBUTING.md`.

---

## Referências

- Produto de referência: <https://seguenoinsta.nucleodigital.cc/>
- Google Takeout: <https://takeout.google.com/>
- Instagram Help Center: <https://help.instagram.com/> (buscar "Baixar suas informações")
- ANPD: <https://www.gov.br/anpd/pt-br>
- Meta for Developers: <https://developers.facebook.com/terms/>
- Docker rootless: <https://docs.docker.com/engine/security/rootless/>
