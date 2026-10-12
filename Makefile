# BKP — atalhos de build e execução (tudo em container; nunca pytest/pip/npm na máquina).

.PHONY: setup dev build test prod prod-down down reset logs

# Prepara o .env a partir do .env.example (não sobrescreve um existente).
setup:
	@test -f .env || cp .env.example .env
	@if ! grep -qE '^JWT_SECRET=.{32,}$$' .env; then \
		echo "⚠  JWT_SECRET ausente ou curto (< 32 chars) no .env — o backend valida no import."; \
	fi

# Sobe o ambiente de dev (API :8000, Mailpit :8025, frontend Vite :3000).
dev: setup
	docker compose up -d --build

# Apenas build das imagens.
build:
	docker compose build

# Testes do backend.
test:
	docker compose exec api pytest

# Ambiente de produção (Caddy como gateway único em :80/:443).
prod:
	docker compose -f docker-compose.yml --profile prod up -d --build

prod-down:
	docker compose -f docker-compose.yml --profile prod down

# Derruba o ambiente de dev.
down:
	docker compose down

# Reset completo (apaga banco, uploads e e-mails).
reset:
	docker compose down -v
	docker compose up -d --build

# Logs (segue a saída).
logs:
	docker compose logs -f
