"""Comando de backoffice: gera links de convite de acesso (sem e-mail).

Uso (no container):
    docker compose exec api python -m app.invite a@b.com c@d.com
    docker compose exec -T api python -m app.invite < emails.txt

Imprime um link por e-mail; o operador distribui os links fora da aplicação.
"""
import os
import sys

from . import services
from .db import SessionLocal


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _emails(args: list[str]) -> list[str]:
    if args:
        return [a.strip().lower() for a in args if a.strip()]
    return [line.strip().lower() for line in sys.stdin if line.strip()]


def main() -> None:
    emails = _emails(sys.argv[1:])
    if not emails:
        print("Informe ao menos um e-mail (argumentos ou stdin).", file=sys.stderr)
        raise SystemExit(2)
    with SessionLocal() as db:
        for email in emails:
            token = services.create_invite(db, email)
            if token is None:
                print(f"{email}: já tem conta ativa — ignorado")
            else:
                print(f"{email}: {_frontend_url()}/invite/{token}")


if __name__ == "__main__":
    main()
