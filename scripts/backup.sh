#!/usr/bin/env bash
# Backup do banco do BKP (pg_dump) com retenção alinhada à política do produto.
#
# Uso:   scripts/backup.sh [dias] [diretório]
# Ex.:   scripts/backup.sh 30 ./backups   # mantém backups dos últimos 30 dias
#
# Roda via container (`docker compose exec db`), seguindo a regra do projeto.
set -euo pipefail

RETENTION_DAYS="${1:-${RETENTION_DAYS:-30}}"
BACKUP_DIR="${2:-${BACKUP_DIR:-./backups}}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/backup-$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
docker compose exec -T db pg_dump -U app -d backup | gzip > "$OUT"
echo "Backup criado: $OUT"

# Retenção: apaga backups com mais de RETENTION_DAYS (mesma janela da retenção LGPD).
find "$BACKUP_DIR" -name 'backup-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
