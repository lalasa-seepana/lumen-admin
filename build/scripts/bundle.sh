#!/usr/bin/env bash
# Create a tarball of the packed build/ ready to scp to a VPS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/clinic-stack-vps.tar.gz}"

if [[ ! -d "$ROOT/apps/backend" || ! -d "$ROOT/apps/lumen" ]]; then
  echo "Run ./scripts/pack.sh first." >&2
  exit 1
fi

tar -czf "$OUT" \
  --exclude '.git' \
  --exclude 'clinic-stack-vps.tar.gz' \
  -C "$(dirname "$ROOT")" \
  "$(basename "$ROOT")"

echo "Wrote $OUT"
echo "On VPS: tar -xzf clinic-stack-vps.tar.gz && cd build && docker compose up -d --build"
