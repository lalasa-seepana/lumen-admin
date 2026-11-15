#!/usr/bin/env bash
# Sync Clinic Dial + Lumen sources into build/apps for a self-contained VPS deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LALA_ROOT="$(cd "$ROOT/.." && pwd)"

if [[ -z "${LUMEN_ROOT:-}" ]]; then
  for candidate in \
    "$HOME/Downloads/lumen-website" \
    "$LALA_ROOT/../lumen-website" \
    "/Users/madhu/Downloads/lumen-website"
  do
    if [[ -f "$candidate/package.json" ]]; then
      LUMEN_ROOT="$(cd "$candidate" && pwd)"
      break
    fi
  done
fi

if [[ -z "${LUMEN_ROOT:-}" || ! -f "${LUMEN_ROOT}/package.json" ]]; then
  echo "Cannot find lumen-website. Set LUMEN_ROOT=/path/to/lumen-website" >&2
  exit 1
fi

echo "Clinic Dial: $LALA_ROOT"
echo "Lumen:       $LUMEN_ROOT"

RSYNC_EXCLUDES=(
  --exclude '.git'
  --exclude 'node_modules'
  --exclude '.next'
  --exclude '.venv'
  --exclude '__pycache__'
  --exclude '.pytest_cache'
  --exclude '.env'
  --exclude '.env.local'
  --exclude '.env.*.local'
  --exclude 'tsconfig.tsbuildinfo'
  --exclude '.DS_Store'
  --exclude '.pnpm-store'
)

sync_dir() {
  local src="$1"
  local dest="$2"
  mkdir -p "$dest"
  rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$src/" "$dest/"
  echo "packed $src -> $dest"
}

sync_dir "$LALA_ROOT/backend" "$ROOT/apps/backend"
sync_dir "$LALA_ROOT/apps/dashboard" "$ROOT/apps/dashboard"
sync_dir "$LALA_ROOT/apps/voice-client" "$ROOT/apps/voice-client"
sync_dir "$LUMEN_ROOT" "$ROOT/apps/lumen"

# Ensure Next public folders exist so Docker COPY never fails
mkdir -p "$ROOT/apps/dashboard/public" "$ROOT/apps/lumen/public"

# Env templates if missing
[[ -f "$ROOT/.env" ]] || cp "$ROOT/.env.example" "$ROOT/.env"
[[ -f "$ROOT/env/backend.env" ]] || cp "$ROOT/env/backend.env.example" "$ROOT/env/backend.env"
[[ -f "$ROOT/env/lumen.env" ]] || cp "$ROOT/env/lumen.env.example" "$ROOT/env/lumen.env"

echo
echo "Pack complete."
echo "1. Edit build/.env, build/env/backend.env, build/env/lumen.env"
echo "2. From build/:  docker compose up -d --build"
echo "3. Or tarball:   ./scripts/bundle.sh"
