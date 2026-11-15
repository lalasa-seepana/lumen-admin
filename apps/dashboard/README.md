# Clinic Dial dashboard (Epics 1–4)

Next.js app for clinic owner auth, website integration keys, and Milestone A CRM modules.

## Design tokens (Epic 4A)

Defined in `app/globals.css` as CSS variables:

| Token | Role |
|---|---|
| `--brand`, `--brand-hover`, `--brand-ink` | Rainforest green primary actions |
| `--lagoon`, `--accent` | Andaman mist + soft temple-gold accents |
| `--bg`, `--bg-deep`, `--surface`, `--line`, `--shadow` | Leaf / mist atmosphere + panels |
| `--ink`, `--muted`, `--danger` | Text + errors |
| `--radius`, `--space-*`, `--focus`, `--motion` | Layout + a11y + motion |
| `--type-display`, `--type-body` | Fraunces + Outfit via `app/layout.tsx` |

Palette direction: Thailand eco (canopy green, lagoon wash, light gold) — not Lumen marketing styles.

Auth UX ships on the live login page first; CRM shell primitives follow in Epic 4.

## Forgot password

Sign-in includes **Forgot password?** → Supabase emails a recovery link back to `http://localhost:3001/`.

In the Clinic Dial Supabase project → **Authentication → URL configuration**:

1. Site URL: `http://localhost:3001`
2. Redirect URLs: include `http://localhost:3001` and `http://localhost:3001/**`

Without those, the reset email may link to the wrong host.

## Setup

1. Create a **Clinic Dial** Supabase project (separate from Lumen).
2. Apply migrations under `../../supabase/migrations/` (clinics + website integrations).
3. Copy env:

```sh
cp .env.example .env.local
```

Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_LALA_API_URL`.

4. Run API (`../../backend`) then:

```sh
pnpm install
pnpm dev
```

Open http://localhost:3001 — after login + clinic create, use Overview / Consultations / Customers / Website integrations / Activity. Appointments, AI, and Analytics show planned empty states (no fake data).
