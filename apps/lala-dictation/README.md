# Lala Dictation

An independent local dictation app. It is not affiliated with or endorsed by Wispr Flow or Willow Voice.

hold **fn** → speak → local Whisper transcription → polish (edit model) → paste into the focused app.

No cloud server required. Everything runs on your Mac.

## How dictation works

Lala Dictation uses two stages:

1. **ASR** — “What words did the user say?”
2. **Edit model / Auto Cleanup** — “What text did they mean to put in the app?”

Transcription uses local `whisper-tiny.en` through Transformers.js. Cleanup applies rules for fillers, punctuation, and spoken corrections such as “actually” and “scratch that”. The result is pasted into the focused field using the clipboard and Cmd+V.

**Light** removes fillers and fixes grammar-ish boundaries. **Medium** also does light clarity rewrites. **None** pastes the raw transcript.

## Install

```sh
cd apps/lala-dictation
npm install
```

`postinstall` compiles `electron/fn-watcher` (Swift) for the fn key.

## Run

```sh
npm start
```

First launch downloads the Whisper speech model into the local model cache. Whisper is the transcription model name, not the app’s brand.

### Permissions (macOS)

1. **Microphone** — for recording
2. **Accessibility** — so paste (Cmd+V) can reach other apps

Tray menu → “Open Accessibility / Microphone Settings”.

### Hotkeys

| Action | Shortcut |
| --- | --- |
| Hold to dictate | **fn** (Globe) |
| Hands-free | Double-tap **fn**, tap again to stop |
| Fallback toggle | **Control+Space** or **Alt+`** |
| Cancel | **Esc** |

Click the **Light** pill on the floating bar to cycle cleanup: None → Light → Medium.

## Test polish without speaking

```sh
npm run test:polish
```

## Notes

- The app and folder were renamed to Lala Dictation and `apps/lala-dictation`.
- Existing preferences and downloaded models are reused from the previous storage locations. Fresh installs use `lala-dictation` storage folders.
