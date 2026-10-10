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
| Parser JSON (Takeout) | ✅ Funcionando (5/5 testes) |
| Parser HTML (Takeout) | ✅ Funcionando |
| Normalização e deduplicação | ✅ Funcionando |
| Análise de integridade (janelas, cobertura) | ✅ Funcionando |
| Autenticação (JWT + Argon2) | ✅ Funcionando |
| Isolamento entre clientes | ✅ Testado |
| Retenção e exclusão (LGPD) | ✅ Implementado |
| Fila assíncrona (Celery + Redis) | ✅ Pronto |
| Exportação CSV/XLSX | ✅ Implementado |
| **Enriquecimento (provider real)** | ⏳ **Pendente** — usando `NullProvider` |
| Frontend | ⏳ Não iniciado |

---

## Stack

**Backend**
- Python 3.14
- FastAPI + Uvicorn
- SQLAlchemy + PostgreSQL 16
- Celery + Redis 7
- PyJWT + argon2-cffi
- openpyxl (XLSX)
- httpx, python-multipart, pydantic-settings
- pytest

**Infraestrutura**
- Docker + Docker Compose
- Armazenamento privado de arquivos (volume local; S3 na produção)

**Frontend (planejado)**
- Next.js (protótipo em Streamlit)

---

## Estrutura do Projeto

```
bkp/
├── README.md
├── docker-compose.yml
├── .env.example
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
    │   ├── auth.py            # Cadastro/login
    │   ├── security.py        # Hash + JWT
    │   ├── rate.py            # Rate limiting
    │   └── providers/         # Fontes de enriquecimento
    │       ├── base.py
    │       ├── null_provider.py
    │       └── (futuro) apify_provider.py
    ├── tests/
    └── tools/                 # Scripts de análise e debug
```

---

## Como Rodar (Docker)

```bash
# 1. Clonar
git clone https://github.com/Ian-Mendes/bkp.git
cd bkp

# 2. Configurar variáveis
cp .env.example .env
# Editar .env com suas senhas

# 3. Subir
docker compose up -d --build

# 4. Rodar testes
docker compose exec api pytest

# 5. Health check
curl http://localhost:8000/health
```

---

## Variáveis de Ambiente (`.env`)

```env
# Banco
POSTGRES_PASSWORD=troque_esta_senha
DATABASE_URL=postgresql+psycopg://app:troque_esta_senha@db:5432/backup

# Fila
REDIS_URL=redis://redis:6379/0

# Segurança (mínimo 32 caracteres)
JWT_SECRET=troque_por_uma_string_aleatoria_com_32_mais_caracteres

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
```

**Nunca comite o `.env` real.** Use `.env.example` como modelo.

---

## Fluxo de Uso da API

```bash
# 1. Registrar
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"voce@exemplo.com","password":"senha-bem-longa-123"}'

# 2. Fazer login (guarda o token)
TOKEN="..."

# 3. Enviar o ZIP do Takeout
curl -X POST http://localhost:8000/orders \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@takeout.zip"

# 4. Iniciar o enriquecimento
curl -X POST http://localhost:8000/orders/$ORDER_ID/start \
  -H "Authorization: Bearer $TOKEN"

# 5. Acompanhar
curl http://localhost:8000/orders/$ORDER_ID \
  -H "Authorization: Bearer $TOKEN"

# 6. Baixar relatório
curl http://localhost:8000/orders/$ORDER_ID/report \
  -H "Authorization: Bearer $TOKEN"

# 7. Baixar planilhas
curl -o backup.csv  http://localhost:8000/orders/$ORDER_ID/export.csv  -H "Authorization: Bearer $TOKEN"
curl -o backup.xlsx http://localhost:8000/orders/$ORDER_ID/export.xlsx -H "Authorization: Bearer $TOKEN"
```

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/auth/register` | Cadastro |
| POST | `/auth/login` | Login |
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
- ✅ Links temporários para download.
- ✅ Retenção configurável (`RETENTION_DAYS`, padrão 30 dias).
- ✅ Limite de tentativas de login (rate limit via Redis).
- ✅ Hash de senha com Argon2id.
- ✅ Neutralização de fórmulas no CSV/XLSX (anti-injeção).

> O envio de uma exportação pelo cliente **não concede automaticamente**
> permissão para uso posterior dos dados de terceiros. Base legal e
> salvaguardas devem ser avaliadas para cada finalidade.

---

## Roadmap

- [x] Parser JSON + HTML
- [x] Autenticação e isolamento
- [x] Fila assíncrona
- [x] Exportação CSV/XLSX
- [ ] **Integração com provedor de enriquecimento (Apify ou similar)**
- [ ] Frontend (Next.js)
- [ ] Página reserva (backup de perfil)
- [ ] CRM leve
- [ ] Agentes de IA para classificação de bios

---

## Como Contribuir

1. Crie uma branch: `git checkout -b feat/nome-da-feature`
2. Commits pequenos e descritivos.
3. Rode os testes antes de abrir PR: `pytest`
4. Abra PR explicando **o quê** e **por quê**.

---

## Referências

- Produto de referência: <https://seguenoinsta.nucleodigital.cc/>
- Google Takeout: <https://takeout.google.com/>
- Instagram Help Center: <https://help.instagram.com/> (buscar "Baixar suas informações")
- ANPD: <https://www.gov.br/anpd/pt-br>
- Meta for Developers: <https://developers.facebook.com/terms/>
