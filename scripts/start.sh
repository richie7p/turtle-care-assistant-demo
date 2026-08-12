#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$project_root/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  echo ".venv was not found. Follow the README installation steps first." >&2
  exit 1
fi

(
  cd "$project_root/frontend"
  npm run build
)

cd "$project_root/backend"
"$python_bin" -m alembic upgrade head
"$python_bin" -m app.cli init-db
exec "$python_bin" -m uvicorn app.main:app \
  --host "${APP_HOST:-127.0.0.1}" \
  --port "${APP_PORT:-8000}"
