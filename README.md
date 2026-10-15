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
- Mailpit (SMTP de desenvolvimento, captura os e-mails)
- Caddy (gateway de produção, perfil `prod`; em dev o Vite serve o frontend)

**Frontend**
- Vite 5 + React 18 (react-router-dom, JavaScript)

---

## Estrutura do Projeto

```
bkp/
├── README.md
├── CONTRIBUTING.md
├── docker-compose.yml          # db, mailpit, api (+ perfil prod com Caddy)
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
    │   ├── auth.py             # Cadastro, login, confirmação de e-mail, recuperação de senha
    │   ├── security.py         # Hash + JWT (sessão e tokens de e-mail)
    │   ├── mailer.py           # Envio SMTP
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
| 1 | `docker compose ps` | 4 serviços `Up` (`api`, `db`, `mailpit`, `frontend`); `db` e `mailpit` com `(healthy)` |
| 2 | `docker compose logs api --tail 20` | Termina com `Application startup complete` e **sem** traceback |
| 3 | `curl -i http://localhost:8000/health` | `HTTP/1.1 200 OK` |
| 4 | `docker compose exec api sh -c 'echo ${#JWT_SECRET}'` | `64` (ou pelo menos `32`) |
| 5 | `docker compose exec db psql -U app -d backup -c '\dt'` | Lista as tabelas (`users`, `orders`, `profiles`), provando que o banco aceita a senha |
| 6 | `docker compose exec api pytest` | `50 passed` |
| 7 | Abrir http://localhost:3000 | Tela de login do frontend |
| 8 | Abrir http://localhost:8025 | Caixa de entrada do Mailpit |

> ⚠️ **O `pytest` passar não prova que o banco está conectado.** Os testes passam mesmo
> quando a API não consegue autenticar no Postgres. Sempre confirme também os passos
> 2, 3 e 5.

Serviços e portas (todos só em localhost):

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API (Swagger em `/docs`, só em desenvolvimento) | http://localhost:8000 |
| Mailpit (e-mails capturados) | http://localhost:8025 |

### 6. Criar a primeira conta

1. Abra http://localhost:3000 e cadastre-se.
2. Abra o Mailpit (http://localhost:8025) e clique no link de confirmação.
3. Na tela que abrir, informe a **senha do cadastro** para ativar a conta.
4. Faça login.

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
| Erro de `column ... does not exist` após atualizar | Não há migrações ainda (`create_all` + `ALTER` pontual) e o banco antigo ficou sem a coluna nova | Em desenvolvimento: `docker compose down -v && docker compose up -d` (apaga os dados) |

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
# Apagar tudo (banco, uploads e e-mails do Mailpit)
docker compose down -v && docker compose up -d

# Só usuários, pedidos e perfis
docker compose exec db psql -U app -d backup -c "TRUNCATE users, orders, profiles RESTART IDENTITY CASCADE;"

# Zerar limites de tentativas (rate limit): o contador é em memória,
# então basta reiniciar a API
docker compose restart api
```

---

## Testar Confirmação de E-mail e Recuperação de Senha

Em desenvolvimento nenhum e-mail sai de verdade. Cadastre-se em http://localhost:3000 e abra
o Mailpit em http://localhost:8025 para clicar no link recebido.

- **Confirmação:** o link abre `/verify-email`, que pede a **senha do cadastro** para ativar a conta.
- **Recuperação:** em "Esqueci minha senha" informe o e-mail; o link do Mailpit vale 30 min e só funciona uma vez.
- **Não chegou e-mail?** Veja `docker compose logs api --tail 30` (o envio roda em `BackgroundTasks`, depois da resposta).
- Cada fluxo (cadastro, reenvio, recuperação) envia no máximo 6 e-mails por hora para o mesmo endereço.
- O login só funciona depois de confirmar o e-mail.

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

O frontend chama a API pela mesma origem (`/api`), encaminhada pelo proxy
(Vite em dev, Caddy em produção) — sem variável a configurar; ver `frontend/.env.example`.

**Nunca comite o `.env` real** (confira se ele está no `.gitignore`). Use `.env.example` como modelo
e gere um `JWT_SECRET` e uma senha de banco diferentes para cada ambiente, principalmente produção.

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
| POST | `/auth/refresh` | Renova o access token a partir do refresh cookie |
| POST | `/auth/logout` | Invalida os cookies de sessão e refresh |
| POST | `/orders` | Upload do ZIP |
| GET | `/orders/upload-config` | Limite de upload em bytes (autenticado) |
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
- ✅ Limite de tentativas de login (rate limit em memória).
- ✅ Confirmação de e-mail obrigatória para entrar (link válido por 24 h) e exige a senha do cadastro, o que impede o pré-sequestro de conta por quem cadastrou o e-mail alheio.
- ✅ Link de redefinição de senha válido por 30 min e de uso único.
- ✅ Trocar a senha (ou fazer logout) derruba as sessões abertas via `token_version`.
- ✅ Sessão em cookie httpOnly (`bkp_session`) com refresh token (`bkp_refresh`); `token_version` permite revogação em massa.
- ✅ Cadastro, reenvio e recuperação não revelam se o e-mail está cadastrado (mesma resposta; quem já tem conta recebe um aviso por e-mail).
- ✅ Teto de 6 e-mails por hora por destinatário em cada fluxo, independente do IP.

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
- ⚠️ Cadastro pendente pode ser sobrescrito por terceiros (só atrapalha, não dá acesso); o desenho definitivo guarda o pendente em tabela própria.

> O envio de uma exportação pelo cliente **não concede automaticamente**
> permissão para uso posterior dos dados de terceiros. Base legal e
> salvaguardas devem ser avaliadas para cada finalidade.

---

## Roadmap

- [x] Parser JSON + HTML
- [x] Autenticação e isolamento
- [x] Exportação CSV/XLSX
- [x] Confirmação de e-mail e recuperação de senha
- [x] Frontend: login, cadastro e recuperação de senha
- [ ] **Integração com provedor de enriquecimento (Apify ou similar)**
- [ ] Fila assíncrona (reintroduzir Celery/Redis com o provider real)
- [x] Frontend: upload do ZIP
- [ ] Frontend: lista de pedidos e downloads
- [ ] Migrações com Alembic (hoje `create_all` + `ALTER` pontual)
- [ ] Provedor SMTP real e domínio (SPF/DKIM) para produção
- [x] Sessão em cookie `httpOnly`, logout e revogação de sessão
- [ ] Cadastro pendente em tabela própria
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
