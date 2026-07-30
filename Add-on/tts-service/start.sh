#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH="$SCRIPT_DIR/.openvoice-env/bin:$PATH"
export PATH
exec "$SCRIPT_DIR/.openvoice-env/bin/uvicorn" app:app \
  --app-dir "$SCRIPT_DIR" \
  --host "${TTS_HOST:-127.0.0.1}" \
  --port "${TTS_PORT:-5001}"
