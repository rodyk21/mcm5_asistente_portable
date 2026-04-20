#!/usr/bin/env sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

: "${MCM5_HOST:=0.0.0.0}"
: "${MCM5_PORT:=8080}"

if [ -x ".venv/bin/python" ]; then
  ./.venv/bin/python launcher.py
  exit 0
fi

if command -v python3 >/dev/null 2>&1; then
  python3 launcher.py
  exit 0
fi

if command -v python >/dev/null 2>&1; then
  python launcher.py
  exit 0
fi

echo "No se ha encontrado Python ni entorno virtual local." >&2
exit 1
