const statusEl = document.getElementById("status");
const barEl = document.getElementById("bar");
const levelEl = document.getElementById("level");

const LEVELS = ["none", "light", "medium"];
const STATUS = {
  idle: "Hold fn to speak",
  listening: "Listening…",
  transcribing: "Transcribing…",
  polishing: "Polishing…",
  done: "Pasted",
  error: "Something went wrong",
  loading: "Loading Whisper…",
};

let mediaStream = null;
let mediaRecorder = null;
let chunks = [];
let cleanupLevel = "light";

function setUi(state, payload = {}) {
  barEl.dataset.state = state;
  barEl.className = `bar ${state}`;
  if (payload.message) statusEl.textContent = payload.message;
  else if (payload.text) statusEl.textContent = truncate(payload.text, 42);
  else statusEl.textContent = STATUS[state] ?? state;
  if (payload.cleanupLevel) {
    cleanupLevel = payload.cleanupLevel;
    levelEl.textContent = capitalize(cleanupLevel);
  }
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function truncate(s, n) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

async function startMic() {
  chunks = [];
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : MediaRecorder.isTypeSupported("audio/mp4")
      ? "audio/mp4"
      : "audio/webm";
  mediaRecorder = new MediaRecorder(mediaStream, { mimeType: mime });
  mediaRecorder.ondataavailable = (e) => {
    if (e.data?.size) chunks.push(e.data);
  };
  mediaRecorder.start(100);
}

function stopMicTracks() {
  mediaStream?.getTracks().forEach((t) => t.stop());
  mediaStream = null;
}

function encodeWav(float32, sampleRate) {
  const numFrames = float32.length;
  const buffer = new ArrayBuffer(44 + numFrames * 2);
  const view = new DataView(buffer);

  const writeStr = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + numFrames * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, numFrames * 2, true);

  let offset = 44;
  for (let i = 0; i < numFrames; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

async function blobToWav16k(blob) {
  const arrayBuf = await blob.arrayBuffer();
  const audioCtx = new AudioContext();
  const decoded = await audioCtx.decodeAudioData(arrayBuf.slice(0));
  const input = decoded.getChannelData(0);
  const targetRate = 16000;
  let samples = input;
  if (decoded.sampleRate !== targetRate) {
    const ratio = decoded.sampleRate / targetRate;
    const newLen = Math.round(input.length / ratio);
    samples = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) samples[i] = input[Math.floor(i * ratio)];
  }
  await audioCtx.close();
  return encodeWav(samples, targetRate);
}

async function finishDictation() {
  try {
    const wavBuffer = await new Promise((resolve, reject) => {
      if (!mediaRecorder || mediaRecorder.state === "inactive") {
        stopMicTracks();
        resolve(null);
        return;
      }
      mediaRecorder.onstop = async () => {
        try {
          stopMicTracks();
          if (!chunks.length) {
            resolve(null);
            return;
          }
          const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
          chunks = [];
          resolve(await blobToWav16k(blob));
        } catch (err) {
          reject(err);
        }
      };
      mediaRecorder.stop();
    });

    if (!wavBuffer) {
      setUi("error", { message: "No speech detected" });
      setTimeout(() => setUi("idle", { cleanupLevel }), 1200);
      return;
    }

    setUi("transcribing");
    await window.lalaDictation.completeAudio(wavBuffer);
  } catch (err) {
    console.error(err);
    setUi("error", { message: err?.message || "Transcription failed" });
    setTimeout(() => setUi("idle", { cleanupLevel }), 1600);
  }
}

levelEl.addEventListener("click", async () => {
  const idx = LEVELS.indexOf(cleanupLevel);
  const next = LEVELS[(idx + 1) % LEVELS.length];
  cleanupLevel = await window.lalaDictation.setCleanup(next);
  levelEl.textContent = capitalize(cleanupLevel);
});

window.lalaDictation.onState((data) => {
  setUi(data.state, data);
});

window.lalaDictation.onDictationStart(async () => {
  try {
    await startMic();
    setUi("listening", { cleanupLevel });
  } catch (err) {
    console.error(err);
    setUi("error", { message: "Mic permission needed" });
    window.lalaDictation.cancel();
  }
});

window.lalaDictation.onDictationStop(() => {
  finishDictation();
});

window.lalaDictation.onDictationCancel(() => {
  try {
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  } catch {
    /* ignore */
  }
  stopMicTracks();
  chunks = [];
  setUi("idle", { cleanupLevel });
});

window.lalaDictation.getSettings().then((s) => {
  cleanupLevel = s.cleanupLevel || "light";
  levelEl.textContent = capitalize(cleanupLevel);
  setUi("idle", { cleanupLevel });
});
