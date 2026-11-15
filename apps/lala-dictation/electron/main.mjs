import {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  Menu,
  nativeImage,
  screen,
  shell,
  Tray,
} from "electron";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Store from "electron-store";
import { polish, CLEANUP_LEVELS } from "./polish.mjs";
import { pasteText } from "./paste.mjs";
import { transcribeWebm, warmAsr } from "./transcribe.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const isDev = process.argv.includes("--dev");

app.setName("Lala Dictation");
// Reuse existing preferences after the rename; fresh installs use the new name.
const legacyUserData = path.join(app.getPath("appData"), "whisper-flow");
const userDataPath = fs.existsSync(legacyUserData)
  ? legacyUserData
  : path.join(app.getPath("appData"), "lala-dictation");
fs.mkdirSync(userDataPath, { recursive: true });
app.setPath("userData", userDataPath);

const store = new Store({
  defaults: {
    cleanupLevel: "light",
    handsFree: false,
    hotkeyFallback: "RightAlt", // used when FN watcher unavailable
  },
});

let overlay = null;
let tray = null;
let fnProc = null;
let recording = false;
let handsFree = false;
let lastFnDownAt = 0;
let processing = false;

function createOverlay() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  overlay = new BrowserWindow({
    width: 420,
    height: 88,
    x: Math.round((width - 420) / 2),
    y: height - 120,
    frame: false,
    transparent: true,
    resizable: false,
    movable: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    focusable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false,
    },
  });

  overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlay.setAlwaysOnTop(true, "screen-saver");
  overlay.loadFile(path.join(ROOT, "renderer", "overlay.html"));

  if (isDev) overlay.webContents.openDevTools({ mode: "detach" });
}

function showOverlay(state, payload = {}) {
  if (!overlay) return;
  if (!overlay.isVisible()) overlay.showInactive();
  overlay.webContents.send("overlay:state", { state, ...payload });
}

function hideOverlaySoon(ms = 900) {
  setTimeout(() => {
    if (!recording && !processing && overlay?.isVisible()) overlay.hide();
  }, ms);
}

async function startListening() {
  if (recording || processing) return;
  recording = true;
  showOverlay("listening", { cleanupLevel: store.get("cleanupLevel") });
  overlay?.webContents.send("dictation:start");
}

async function stopListening({ cancel = false } = {}) {
  if (!recording) return;
  recording = false;
  handsFree = false;

  if (cancel) {
    overlay?.webContents.send("dictation:cancel");
    showOverlay("idle");
    hideOverlaySoon(200);
    return;
  }

  processing = true;
  showOverlay("transcribing");
  overlay?.webContents.send("dictation:stop");
}

function onFnDown() {
  const now = Date.now();
  // Double-tap within 350ms → hands-free mode
  if (now - lastFnDownAt < 350) {
    lastFnDownAt = now;
    if (!recording) {
      handsFree = true;
      startListening();
    } else if (handsFree) {
      stopListening();
    }
    return;
  }
  lastFnDownAt = now;
  if (!handsFree) startListening();
}

function onFnUp() {
  if (handsFree) return;
  // Ignore very short taps used for double-tap detection
  if (Date.now() - lastFnDownAt < 180) return;
  stopListening();
}

function startFnWatcher() {
  const bin = path.join(__dirname, "fn-watcher");
  if (!fs.existsSync(bin)) {
    console.warn("[lala-dictation] fn-watcher missing; using Right Option fallback");
    registerFallbackHotkey();
    return;
  }

  fnProc = spawn(bin, [], { stdio: ["ignore", "pipe", "pipe"] });
  let buf = "";
  fnProc.stdout.on("data", (chunk) => {
    buf += chunk.toString();
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim() === "down") onFnDown();
      if (line.trim() === "up") onFnUp();
    }
  });
  fnProc.on("exit", (code) => {
    console.warn("[lala-dictation] fn-watcher exited", code);
    registerFallbackHotkey();
  });
}

function registerFallbackHotkey() {
  // Hold Right Option (AltRight) as FN stand-in when needed
  globalShortcut.unregisterAll();
  const ok = globalShortcut.register("Alt+`", () => {
    // toggle hands-free with Alt+`
    if (recording) stopListening();
    else {
      handsFree = true;
      startListening();
    }
  });
  if (!ok) console.warn("[lala-dictation] failed to register Alt+` fallback");

  // Also: Right Option alone isn't reliably catchable via globalShortcut.
  // Offer Control+Space as press-and-release toggle.
  globalShortcut.register("Control+Space", () => {
    if (recording) stopListening();
    else {
      handsFree = true;
      startListening();
    }
  });
}

function buildTray() {
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setTitle("WF");
  tray.setToolTip("Lala Dictation — hold FN to dictate");

  const level = store.get("cleanupLevel");
  const menu = Menu.buildFromTemplate([
    { label: "Lala Dictation (local)", enabled: false },
    { type: "separator" },
    {
      label: "Auto Cleanup",
      submenu: CLEANUP_LEVELS.map((l) => ({
        label: l[0].toUpperCase() + l.slice(1),
        type: "radio",
        checked: l === level,
        click: () => {
          store.set("cleanupLevel", l);
          showOverlay("idle", { cleanupLevel: l });
        },
      })),
    },
    {
      label: "Dictate (hands-free)",
      click: () => {
        handsFree = true;
        startListening();
      },
    },
    { type: "separator" },
    {
      label: "Open Accessibility Settings",
      click: () =>
        shell.openExternal(
          "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ),
    },
    {
      label: "Open Microphone Settings",
      click: () =>
        shell.openExternal(
          "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
        ),
    },
    { type: "separator" },
    { label: "Quit", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
}

ipcMain.handle("settings:get", () => ({
  cleanupLevel: store.get("cleanupLevel"),
}));

ipcMain.handle("settings:setCleanup", (_e, level) => {
  if (CLEANUP_LEVELS.includes(level)) store.set("cleanupLevel", level);
  return store.get("cleanupLevel");
});

ipcMain.handle("polish:run", (_e, raw) => {
  return polish(raw ?? "", store.get("cleanupLevel"));
});

async function finishWithText(rawText) {
  processing = true;
  showOverlay("polishing");
  const result = polish(rawText ?? "", store.get("cleanupLevel"));
  showOverlay("done", { text: result.polished, raw: result.raw });

  try {
    await pasteText(result.polished);
  } catch (err) {
    console.error("[lala-dictation] paste failed", err);
    showOverlay("error", { message: "Paste failed — grant Accessibility" });
  }

  processing = false;
  hideOverlaySoon(1200);
  return result;
}

ipcMain.handle("dictation:complete", async (_e, rawText) => finishWithText(rawText));

ipcMain.handle("dictation:completeAudio", async (_e, arrayBuffer) => {
  processing = true;
  showOverlay("transcribing");
  try {
    const raw = await transcribeWebm(arrayBuffer, {
      onProgress: (p) => {
        if (p?.status === "progress") {
          showOverlay("loading", {
            message: `Loading Whisper… ${Math.round(p.progress || 0)}%`,
          });
        }
      },
    });
    if (!raw) {
      showOverlay("error", { message: "No speech detected" });
      processing = false;
      hideOverlaySoon(1200);
      return { raw: "", polished: "", level: store.get("cleanupLevel") };
    }
    return await finishWithText(raw);
  } catch (err) {
    console.error("[lala-dictation] transcribe failed", err);
    showOverlay("error", { message: err?.message || "Transcription failed" });
    processing = false;
    hideOverlaySoon(1600);
    throw err;
  }
});

ipcMain.on("dictation:level", (_e, level) => {
  showOverlay(level);
});

ipcMain.on("overlay:cancel", () => stopListening({ cancel: true }));

app.whenReady().then(() => {
  if (process.platform === "darwin") {
    app.dock?.hide();
  }
  createOverlay();
  buildTray();
  startFnWatcher();
  // Escape cancels via global shortcut when overlay is up
  globalShortcut.register("Escape", () => {
    if (recording || processing) stopListening({ cancel: true });
  });
  console.log("[lala-dictation] ready — hold FN (or Control+Space) to dictate");
  warmAsr((p) => {
    if (p?.status === "ready") console.log("[lala-dictation] whisper model ready");
  }).catch((err) => console.warn("[lala-dictation] model warm failed", err?.message));
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  if (fnProc) fnProc.kill();
});

app.on("window-all-closed", (e) => e.preventDefault());
