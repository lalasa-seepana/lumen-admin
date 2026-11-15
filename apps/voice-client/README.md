# Clinic Dial visitor receptionist

Browser client for clinic visitors (no owner JWT).

## Run

```sh
pnpm install
pnpm dev
```

Open http://127.0.0.1:3002/?clinic=`<slug-or-uuid>`.

Optional: set `window.LALA_API_URL` before the module loads (default `http://127.0.0.1:8000`).

## Controls

- **Start conversation** — creates a public visitor session + WebSocket
- **Tap to talk / Send voice** — tap to record, then tap again to send 16 kHz PCM. The microphone stays off until you tap to talk.
- **Type a message** — `{type:"text"}` channel (works when mic is blocked)
- **Language** — EN/HI/TE mid-session
- **Consent** — optional retention; exact product label in the UI
- **Mute / End**

## Modes

| Mode | When | Behaviour |
|------|------|-----------|
| Demo | Missing Gnani | Silent mock STT/TTS; labeled in UI |
| Speech only | Gnani key, no LLM | Real STT/TTS + mock brain replies (audible) |
| Live | Gnani + OpenAI (`LLM_*`) | Real STT/TTS + OpenAI conversation via backend only |

Credentials never appear in this app.

## Noise

Browser echo cancellation and noise suppression are requested. Dedicated Gnani noise-cancellation parameters are not used (undocumented for this integration).
