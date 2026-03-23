#!/usr/bin/env bash
# Configura cron jobs para scrapshe
# Uso: bash scripts/setup_cron.sh /caminho/absoluto/para/scrapshe

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: bash scripts/setup_cron.sh /caminho/absoluto/para/scrapshe" >&2
    exit 1
fi

PROJECT_DIR="$1"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Erro: diretório não encontrado: $PROJECT_DIR" >&2
    exit 1
fi

# Cria diretório de logs se não existir
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Detecta binário go compilado
GO_BIN="$PROJECT_DIR/scrapers/bin/scrapshe"
if [ ! -f "$GO_BIN" ]; then
    echo "Aviso: binário Go não encontrado em $GO_BIN" >&2
    echo "Execute: cd $PROJECT_DIR/scrapers && go build -o bin/scrapshe ./cmd/scrapshe" >&2
fi

# Detecta python3
PYTHON_BIN="$(command -v python3 2>/dev/null || echo '')"
if [ -z "$PYTHON_BIN" ]; then
    echo "Erro: python3 não encontrado no PATH" >&2
    exit 1
fi

# Monta as novas entradas de cron
CRON_GO="0 3 * * * $GO_BIN >> $LOG_DIR/scrapers.log 2>&1"
CRON_PY="0 4 * * * $PYTHON_BIN $PROJECT_DIR/pipeline/run.py >> $LOG_DIR/pipeline.log 2>&1"

# Preserva crontab existente e adiciona as novas entradas (evita duplicatas)
TMPFILE="$(mktemp)"
crontab -l 2>/dev/null | grep -v "scrapshe\|$GO_BIN\|pipeline/run.py" > "$TMPFILE" || true

echo "$CRON_GO" >> "$TMPFILE"
echo "$CRON_PY" >> "$TMPFILE"

crontab "$TMPFILE"
rm -f "$TMPFILE"

echo "Cron jobs configurados com sucesso:"
echo "  $CRON_GO"
echo "  $CRON_PY"
echo "Logs em: $LOG_DIR"
