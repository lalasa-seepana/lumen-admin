#!/bin/sh
set -eu
if [ -n "${LALA_API_URL:-}" ]; then
  printf 'window.LALA_API_URL = "%s";\n' "$LALA_API_URL" > /usr/share/nginx/html/config.js
else
  printf '/* no LALA_API_URL override */\n' > /usr/share/nginx/html/config.js
fi
