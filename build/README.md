# VPS build pack — Clinic Dial + Lumen

Self-contained folder for deploying both projects on one VPS with Docker + nginx.

| Service | Source | Internal port | Default host |
|---------|--------|---------------|--------------|
| Lumen website | `lumen-website` | 3000 | `lumen.localhost` |
| Clinic Dial dashboard | `lala/apps/dashboard` | 3001 | `app.localhost` |
| Visitor voice UI | `lala/apps/voice-client` | 80 | `voice.localhost` |
| Clinic Dial API | `lala/backend` | 8000 | `api.localhost` |
| nginx proxy | this folder | `${HTTP_PORT}` → 80 | — |

## Quick start

```sh
# From this directory
./scripts/pack.sh          # sync both projects into apps/
# edit .env, env/backend.env, env/lumen.env
docker compose up -d --build
```

Point DNS (or `/etc/hosts`) at the VPS for the four hosts in `.env`, or set them to your real subdomains (e.g. `lumen.seepana.com`).

## Ship to a VPS

```sh
./scripts/pack.sh
./scripts/bundle.sh
scp clinic-stack-vps.tar.gz user@vps:/opt/
# on VPS
cd /opt && tar -xzf clinic-stack-vps.tar.gz && cd build
# fill env files, then:
docker compose up -d --build
```

Requires Docker Engine + Compose plugin on the VPS. TLS: put Caddy/certbot in front of port 80, or terminate TLS on the host nginx and proxy to `HTTP_PORT`.

## Env files

- `.env` — hosts + public dashboard build args
- `env/backend.env` — FastAPI / Supabase / voice providers
- `env/lumen.env` — Lumen DB + form secret + allowed origins

Never commit real secrets. `apps/` is gitignored; regenerate with `pack.sh`.

## Layout

```
build/
  apps/           # packed sources (from pack.sh)
  docker/         # Dockerfiles
  nginx/          # reverse proxy
  env/            # runtime env templates
  scripts/pack.sh
  scripts/bundle.sh
  docker-compose.yml
```
