# Lala — Auth & UX Walkthrough (Epic 4A)

Hands-on path through the **shipped** dashboard login baseline. Use this after the live auth UI exists — not as a pre-build design exercise.

Companion to `DEMO_RUNBOOK.md` (full stakeholder demo). This doc covers only: load → sign up / sign in → create clinic → workspace placeholder.

---

## When to use

| Audience | Use |
|---|---|
| Engineer | Verify Epic 4A auth gate before building CRM modules |
| Product / design | Review copy, hierarchy, and mode switching on real UI |
| Stakeholder (short) | 2–3 minute “how an owner gets in” before the full demo |

---

## Prerequisites

| Check | Detail |
|---|---|
| Dashboard | `cd ./lala/apps/dashboard && pnpm dev` → http://localhost:3001 |
| API | `cd ./lala/backend && uvicorn app.main:app --reload --port 8000` |
| Env | Dashboard `.env.local`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_LALA_API_URL` |
| Test identity | Prefer `demo-*@example.com`; clinic names like `Demo Clinic A` |

If Supabase project / live DB is blocked, note the blocker and still walk **logged-out** screens (steps 1–3).

---

## Walkthrough (≈3 minutes)

### 1 — Cold load (≈15s)

**Open:** http://localhost:3001  

**Expect:**
- Brief “Loading your session…” with brand **Lala**, same composition as login
- Then Sign in screen (no session)

**Call out:** First viewport is brand-first — **Lala** is the hero, not a nav chip.

---

### 2 — Sign in screen (≈45s)

**Expect:**
| Element | Role |
|---|---|
| **Lala** (`h1`) | Product brand |
| One lede | Purpose: manage clinic enquiries / customers / operations |
| Panel title **Sign in** | Clear mode |
| Hint | Clinic owners; isolated tenants |
| Email + Password | Required fields |
| One primary button | **Sign in** only |
| Text under form | “Need an account? **Sign up**” — not a second CTA button |

**Do:** Tab through fields; confirm focus ring is visible.  
**Do not:** Invent metrics or open CRM modules (not shipped yet).

---

### 3 — Sign up mode (≈30s)

**Do:** Click **Sign up**.

**Expect:**
- Panel title → **Create account**
- Hint mentions password ≥ 8 characters
- Field hint under password
- Primary button → **Create account**
- Switch text → “Already have an account? **Sign in**”

**Optional:** Submit empty → browser required validation.  
**Optional:** Sign up with `demo-owner-a@example.com` / password ≥ 8 chars.

---

### 4 — Create clinic (≈45s)

**When:** Authenticated but `GET /v1/me` has no clinic.

**Expect:**
- Brand + lede about finishing onboarding (timezone default **Asia/Kolkata**)
- Panel **Create your clinic**
- Signed-in email shown
- Clinic name field (placeholder e.g. Demo Clinic A)
- Primary **Create clinic**
- **Sign out** as text action (escape hatch)

**Do:** Create `Demo Clinic A`.

---

### 5 — Workspace placeholder (≈30s)

**Expect:**
- Clinic **name** from API as the workspace title (not “Lumen”)
- Role + timezone meta
- **Sign out**
- Honest copy that CRM modules arrive in Epic 4 — no fake enquiry counts

**Call out:** This is the Epic 4A auth gate. Epic 4 adds Overview / Consultations / Customers / Integrations / Activity on the same tokens.

---

### 6 — Sign out → restore (≈15s)

**Do:** Sign out → land on Sign in.  
**Optional:** Sign in again → session restore should skip signup and land on clinic workspace (or create-clinic if none).

---

## UX checklist (Epic 4A auth gate)

- [ ] Brand **Lala** is the strongest text on the first viewport  
- [ ] One primary CTA per auth mode; mode switch is text, not a rival button  
- [ ] Errors use `role="alert"` / live region when auth fails  
- [ ] Busy states disable controls and change button label  
- [ ] Loading session uses the same brand composition  
- [ ] Clinic name appears after onboard — never hard-coded Lumen  
- [ ] No fabricated stats on placeholder workspace  
- [ ] Mobile width (~375px): no horizontal overflow  

---

## Design tokens in play

See `./lala/apps/dashboard/README.md` and `app/globals.css`:

- Colour / surface: `--brand`, `--bg`, `--surface`, `--ink`, `--muted`, `--danger`
- Type: Fraunces (display) + Outfit (body) via `app/layout.tsx`
- Motion: short panel rise on `main.auth`; focus ring `--focus`

---

## Out of this walkthrough

| Topic | Where |
|---|---|
| Lumen enquiry → Lala CRM full demo | `DEMO_RUNBOOK.md` |
| Integration keys, appointments, voice | Epics 2–7 / Milestone B–C |
| CRM nav + list/detail modules | Epic 4 (after this gate) |
| Dual-clinic isolation script | `DEMO_RUNBOOK.md` + Epic 8 |

---

## Definition of “walkthrough done”

You completed steps 1–5 on the live app (or documented a real env blocker for steps 4–5) and ticked the UX checklist. That unlocks Epic 4 module work on these tokens — not a separate brand/walkthrough project.
