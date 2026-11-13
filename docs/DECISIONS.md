# Lala — Open Decisions

Track product/architecture choices that block or shape implementation.  
Status: `Open` | `Decided` | `Deferred`. Update the **Decision** column when you choose; leave evidence in **Notes**.

Related: `PRD.md` §13/§17, `EPICS.md` Epic 6, `POC_ROADMAP.md` Milestone C.

---

## How to use

1. Work top → bottom (P0 first).
2. When decided, set Status → `Decided`, fill Decision + date.
3. Do not start the dependent epic/milestone until its P0 blockers are Decided or explicitly Deferred.

---

## Decision log

| ID | Priority | Topic | Question | Options / recommendation | Blocks | Status | Decision | Owner | Notes |
|---|---|---|---|---|---|---|---|---|---|
| D01 | P0 | Retention | How long to keep voice recordings and transcripts? | **Recommend 90 days**, then hard-delete or anonymise; support deletion-on-request (DPDP-aware, not legal advice) | Epic 7, compliance copy | Open | | You | Confirm period + deletion approach |
| D02 | P0 | Lumen → Lala retry | Keep recommended forward retry? | **Recommend:** local save first; forward up to **2** attempts with short backoff; `forward_status` = `forwarded` \| `rejected` \| `pending`; no retry on 4xx; visitor success on local save | Epics 2–3 | Open | | You | Fits current Lumen `saveEnquiry` flow |
| D03 | P0 | Gnani Speech key | Generate and store a Gnani Speech API key? | Create at https://app.gnani.ai/; put in Lala server env as `GNANI_API_KEY` (maps to `X-API-Key-ID`); never browser / `NEXT_PUBLIC_*` | Milestone C / Epic 6 | Open | | You | Required for real STT/TTS |
| D04 | P0 | Evon HF access | Accept gated Hugging Face access for Evon v3.3? | Accept terms on the model page; download only after approval | Milestone C / Epic 6 | Open | | You | Page: https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B |
| D05 | P0 | Evon repo ID | Which Hugging Face repo ID to download/serve? | URL/repo listing: `gnani/gnani-evon-v3.3-30B-A3B`. Snippets/citation often use `gnani/gnani-evon-v3.3`. **Use the exact ID on the page you accept.** | GPU provisioning, `LLM_MODEL` path | Open | | You | Flagged mismatch in PRD |
| D06 | P0 | Evon GPU host | Where to host Evon (cost + provider)? | Needs NVIDIA **H100 80GB / H200 / A100**, Linux; serve with **vLLM ≥0.12** or **SGLang**. Will **not** run on a normal laptop. Expose OpenAI-compatible `/v1/chat/completions` → Lala `LLM_BASE_URL` | Milestone C / Epic 6 | Open | | You | Cost decision; `HF_TOKEN` stays on GPU host only |
| D07 | P1 | Demo scope | Does the first stakeholder demo include Milestone C? | **A+B only** (safer) vs **A+B+C** (needs D03–D06 done) | Demo runbook, Epic 8 | Open | | You | A+B must work alone either way |
| D08 | P1 | TTS voices | Which Timbre voices for EN / HI / TE? | TE examples: Suhana, Lehara, Lavanya, Yukti, Varuni. Pick EN/HI from https://docs.gnani.ai/api/TTS/available-voices → env `GNANI_TTS_VOICE_EN/HI/TE` | Epic 6 polish | Open | | You | Can default later; not needed for A/B |
| D09 | P1 | STT/TTS models | Confirm production model strings | STT: `prisma-v3.0` (with `indic-auto`) vs default `prisma-v2.5`. TTS: **recommend `timbre-v2.5`** | Epic 6 env defaults | Open | | You | Documented defaults in PRD |
| D10 | P1 | HMAC signing | Add request HMAC + timestamp on website integration? | Documented as **P1 after Milestone A**; Bearer key is enough for POC | Epic 2 follow-up | Deferred | Skip for A; revisit after A | You | Optional anti-replay |
| D11 | P2 | Clinic timezone default | Keep `Asia/Kolkata` as default? | **Recommend yes** for POC clinics | Epic 1 / 5 | Decided | Default `Asia/Kolkata`; optional override on `POST /v1/clinics` (2026-11-13) | You | Implemented in Epic 1 |
| D12 | P2 | Analytics depth | Milestone D = minimal real counts only? | **Recommend yes** — enquiry/appointment counts from SQL; no fake revenue | Epic 8 | Open | | You | Matches non-goals |

---

## Suggested order of attack

```text
D02 (retry) ──► start Epic 1–3 when ready to build
D01 (retention) ──► before Epic 7 schema/copy
D07 (demo scope) ──► sets whether C is on the critical path
D03 → D04 → D05 → D06 ──► required chain before Epic 6 live work
D08 / D09 ──► while wiring voice env
D10 / D11 / D12 ──► when convenient
```

---

## Quick checklist (tick in chat or edit Status above)

- [ ] D01 Retention period + deletion approach  
- [ ] D02 Confirm Lumen forward retry + `forward_status`  
- [ ] D03 Gnani API key created and stored server-side  
- [ ] D04 Hugging Face Evon access approved  
- [ ] D05 Exact Evon repo ID chosen  
- [ ] D06 GPU host / provider / budget chosen  
- [ ] D07 First demo includes C? yes / no  
- [ ] D08 TTS voices EN/HI/TE  
- [ ] D09 STT/TTS model strings  
- [ ] D10 HMAC after A? keep deferred or schedule  
- [x] D11 Timezone default `Asia/Kolkata`  
- [ ] D12 Minimal analytics only for D  

---

## Decided archive

_Move rows here when Status becomes Decided (optional copy for history)._

| ID | Decision | Date | Notes |
|---|---|---|---|
| D11 | Default clinic timezone `Asia/Kolkata`; per-clinic override allowed | 2026-11-13 | Epic 1 `POST /v1/clinics` |
