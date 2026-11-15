const params = new URLSearchParams(window.location.search);
const clinicParam = params.get("clinic") || params.get("slug") || "";

const STORAGE_MIC = "lala.visitor.micId";
const STORAGE_SPEAKER = "lala.visitor.speakerId";

const els = {
  clinicName: document.getElementById("clinicName"),
  aiDisclosure: document.getElementById("aiDisclosure"),
  modeBadge: document.getElementById("modeBadge"),
  language: document.getElementById("language"),
  consent: document.getElementById("consent"),
  start: document.getElementById("start"),
  talk: document.getElementById("talk"),
  mute: document.getElementById("mute"),
  stop: document.getElementById("stop"),
  textInput: document.getElementById("textInput"),
  sendText: document.getElementById("sendText"),
  stateBanner: document.getElementById("stateBanner"),
  stage: document.getElementById("stage"),
  stageCaption: document.getElementById("stageCaption"),
  turns: document.getElementById("turns"),
  error: document.getElementById("error"),
  micSelect: document.getElementById("micSelect"),
  speakerSelect: document.getElementById("speakerSelect"),
  refreshDevices: document.getElementById("refreshDevices"),
  testSpeaker: document.getElementById("testSpeaker"),
};

const API_BASE = (window.LALA_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const PCM_SAMPLE_RATE = 16000;

let socket = null;
let visitorToken = null;
let clinicMeta = null;
let sessionActive = false;
let outputMuted = false;

let micStream = null;
let micAudioContext = null;
let micProcessor = null;
let micSource = null;
let micSilentGain = null;
let pcmChunks = [];
let isRecording = false;
let recordingAttempt = 0;
let selectedMicId = localStorage.getItem(STORAGE_MIC) || "";
let selectedSpeakerId = localStorage.getItem(STORAGE_SPEAKER) || "";

let playbackCtx = null;
let playbackDest = null;
let currentSource = null;
let audioQueue = [];
let queuePlaying = false;
let turnAudioHandled = false;
let audioUnlocked = false;

function setState(label, className = "idle") {
  if (className === "listening" && !isRecording) {
    label = "Ready for your next question";
    className = "ready";
  }
  els.stateBanner.textContent = label;
  els.stateBanner.className = `visitor-state ${className}`.trim();
  els.stage.dataset.mode = className || "idle";
  document.getElementById("voiceStatus").textContent = {
    idle: "Ready to start", ready: "Your turn",
    listening: "Recording your message", processing: "One moment…",
    speaking: outputMuted ? "Sound off" : "Receptionist speaking",
    reconnecting: "Disconnected", error: "Needs attention",
  }[className] || "Ready to start";
}

function setCaption(text) {
  els.stageCaption.textContent = text || "";
}

function syncConversationControls() {
  els.start.hidden = sessionActive;
  els.talk.hidden = !sessionActive;
  document.querySelector(".call-controls").dataset.active = String(sessionActive);
  document.getElementById("startLabel").textContent = "Start conversation";
  document.getElementById("voiceHelp").textContent = sessionActive
    ? "Tap to talk, then tap again to send. You can also type below."
    : "Use your voice or type. You choose when the mic is on.";
  document.getElementById("messageHint").textContent = sessionActive
    ? "Press Enter to send · Shift + Enter for a new line."
    : "Start a conversation to send a message.";
}

function showError(message) {
  els.error.hidden = !message;
  els.error.textContent = message || "";
  if (message) setState("Something went wrong", "error");
}

function addTurn(role, text) {
  const li = document.createElement("li");
  const roleEl = document.createElement("span");
  roleEl.className = "role";
  roleEl.textContent = role;
  const body = document.createElement("div");
  body.textContent = text;
  li.append(roleEl, body);
  els.turns.append(li);
  document.getElementById("transcriptPanel").open = true;
}

function wsOrigin() {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.origin;
}

function fillDeviceSelect(select, devices, selectedId, placeholder) {
  const previous = selectedId || select.value || "";
  select.innerHTML = "";
  const def = document.createElement("option");
  def.value = "";
  def.textContent = placeholder;
  select.append(def);
  for (const device of devices) {
    const opt = document.createElement("option");
    opt.value = device.deviceId;
    opt.textContent = device.label || `${placeholder} (${device.deviceId.slice(0, 6)})`;
    select.append(opt);
  }
  if (previous && [...select.options].some((o) => o.value === previous)) {
    select.value = previous;
  } else {
    select.value = "";
  }
}

async function refreshDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const devices = await navigator.mediaDevices.enumerateDevices();
  const mics = devices.filter((d) => d.kind === "audioinput");
  const speakers = devices.filter((d) => d.kind === "audiooutput");
  fillDeviceSelect(els.micSelect, mics, selectedMicId, "Default microphone");
  fillDeviceSelect(els.speakerSelect, speakers, selectedSpeakerId, "Default speaker");
  selectedMicId = els.micSelect.value;
  selectedSpeakerId = els.speakerSelect.value;
  els.micSelect.disabled = mics.length === 0;
  const canSelectOutput = typeof HTMLAudioElement !== "undefined" && "setSinkId" in HTMLAudioElement.prototype;
  els.speakerSelect.disabled = !canSelectOutput && speakers.length === 0;
  if (!canSelectOutput) {
    els.speakerSelect.title = "This browser may not support choosing a speaker (setSinkId).";
  }
}

async function ensurePlaybackUnlocked() {
  if (!playbackCtx) {
    playbackCtx = new AudioContext();
  }
  if (playbackCtx.state === "suspended") {
    await playbackCtx.resume();
  }
  if (selectedSpeakerId && typeof playbackCtx.setSinkId === "function") {
    try {
      await playbackCtx.setSinkId(selectedSpeakerId);
    } catch (err) {
      console.warn("AudioContext.setSinkId failed", err);
    }
  }
  audioUnlocked = true;
}

async function applySpeakerSink(audioEl) {
  if (!selectedSpeakerId || !audioEl?.setSinkId) return;
  try {
    await audioEl.setSinkId(selectedSpeakerId);
  } catch (err) {
    console.warn("setSinkId failed", err);
  }
}

async function loadClinic() {
  if (!clinicParam) {
    els.clinicName.textContent = "Clinic link needed";
    els.aiDisclosure.textContent =
      "Open this page from your clinic’s receptionist link, or add ?clinic= followed by the clinic id or slug.";
    els.start.disabled = true;
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/v1/visitor/clinic/${encodeURIComponent(clinicParam)}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body?.detail?.message || `We could not find that clinic (${res.status}).`);
    }
    clinicMeta = body;
    els.clinicName.textContent = body.name;
    els.aiDisclosure.textContent =
      body.ai_disclosure ||
      `You are chatting with Rhea, an AI receptionist for ${body.name}, not a clinician.`;
    document.title = `${body.name} · Rhea`;
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
    els.start.disabled = true;
  }
}

function pcmToWav(pcmBytes, sampleRate = PCM_SAMPLE_RATE) {
  const dataLength = pcmBytes.byteLength;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);
  const writeStr = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
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
  view.setUint32(40, dataLength, true);
  new Uint8Array(buffer, 44).set(pcmBytes);
  return buffer;
}

function stopSpeaking() {
  audioQueue = [];
  queuePlaying = false;
  if (currentSource) {
    try {
      currentSource.stop();
    } catch {
      /* already stopped */
    }
    currentSource = null;
  }
}

function playAudioBase64(b64, contentType) {
  if (!b64 || outputMuted) {
    if (sessionActive) setState("Listening", "listening");
    return;
  }
  stopSpeaking();
  enqueueAudio(b64, contentType);
}

function enqueueAudio(b64, contentType) {
  if (!b64 || outputMuted) return;
  audioQueue.push({ b64, contentType });
  if (!queuePlaying) void drainAudioQueue();
}

async function drainAudioQueue() {
  if (queuePlaying) return;
  queuePlaying = true;
  setState("Speaking…", "speaking");
  while (audioQueue.length) {
    const next = audioQueue.shift();
    const ok = await playOneClip(next.b64, next.contentType);
    if (!ok) break;
  }
  queuePlaying = false;
  if (sessionActive) setState("Listening", "listening");
}

function decodeBase64(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function playOneClip(b64, contentType) {
  try {
    await ensurePlaybackUnlocked();
    let bytes = decodeBase64(b64);
    let mime = contentType || "audio/wav";
    if (!mime || mime === "audio/pcm" || mime === "application/octet-stream") {
      bytes = new Uint8Array(pcmToWav(bytes));
      mime = "audio/wav";
    }

    // Prefer Web Audio decode for reliable playback after unlock.
    try {
      const copy = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      const audioBuffer = await playbackCtx.decodeAudioData(copy);
      await new Promise((resolve, reject) => {
        const source = playbackCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(playbackCtx.destination);
        currentSource = source;
        source.onended = () => {
          if (currentSource === source) currentSource = null;
          resolve();
        };
        try {
          source.start(0);
        } catch (err) {
          reject(err);
        }
      });
      return true;
    } catch (decodeErr) {
      console.warn("decodeAudioData failed, falling back to HTMLAudioElement", decodeErr);
    }

    const blob = new Blob([bytes], { type: mime });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await applySpeakerSink(audio);
    await new Promise((resolve, reject) => {
      const done = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.addEventListener("ended", done);
      audio.addEventListener("error", () => reject(new Error("Audio playback failed")));
      void audio.play().then(null, reject);
    });
    return true;
  } catch (err) {
    showError(
      err instanceof Error
        ? `Could not play receptionist audio: ${err.message}. Click Test speaker, check Mute, and pick a speaker.`
        : "Could not play receptionist audio.",
    );
    return false;
  }
}

async function playTestTone() {
  try {
    await ensurePlaybackUnlocked();
    const duration = 0.35;
    const sampleRate = playbackCtx.sampleRate;
    const frameCount = Math.floor(sampleRate * duration);
    const buffer = playbackCtx.createBuffer(1, frameCount, sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frameCount; i++) {
      data[i] = Math.sin((2 * Math.PI * 440 * i) / sampleRate) * 0.2;
    }
    await new Promise((resolve) => {
      const source = playbackCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(playbackCtx.destination);
      source.onended = resolve;
      source.start(0);
    });
    setCaption("Speaker test played (440 Hz). If silent, pick another speaker or check system volume.");
  } catch (err) {
    showError(err instanceof Error ? err.message : "Speaker test failed.");
  }
}

function connectSocket(wsPath, token) {
  return new Promise((resolve, reject) => {
    const url = `${wsOrigin()}${wsPath}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.addEventListener("open", () => resolve(ws));
    ws.addEventListener("error", () =>
      reject(new Error("We could not connect to the receptionist. Check your connection and try again.")),
    );
  });
}

function bookingAnnounced(msg) {
  if (msg.booking_confirmed === true) return true;
  if (msg.booking_confirmed === false) return false;
  for (const tool of msg.tool_results || []) {
    if (tool?.tool !== "create_appointment" || !tool.accepted) continue;
    const result = tool.result || {};
    if (result.appointment_id && (result.status === "booked" || result.status === "rescheduled")) {
      return true;
    }
  }
  return false;
}

function handleTurnMessage(msg) {
  if (msg.user_text) {
    addTurn("You", msg.user_text);
    setCaption(`You: ${msg.user_text}`);
  }
  if (msg.assistant_text) {
    addTurn("Receptionist", msg.assistant_text);
    setCaption(msg.assistant_text);
  }
  if (bookingAnnounced(msg)) {
    addTurn("System", "Your appointment is confirmed and saved with the clinic.");
  }
  for (const tool of msg.tool_results || []) {
    if (tool?.tool === "escalate" && tool.accepted) {
      addTurn("System", "A team member has been asked to help you.");
    }
  }
  if (!turnAudioHandled && msg.audio_base64) {
    playAudioBase64(msg.audio_base64, msg.audio_content_type);
  } else if (sessionActive && !queuePlaying && !audioQueue.length) {
    setState("Listening", "listening");
  }
  turnAudioHandled = false;
}

function sendJson(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(payload));
  return true;
}

function syncLanguage() {
  if (!sessionActive) return;
  sendJson({ type: "set_language", language: els.language.value });
}

function syncConsent() {
  if (!sessionActive) return;
  sendJson({ type: "set_consent", recording_consent: els.consent.checked });
}

function bindSocket(ws) {
  socket = ws;
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "ready") {
      const mode = msg.mode || "mock";
      if (mode === "live") {
        els.modeBadge.hidden = false;
        const providerLabel = {
          openai: "OpenAI",
          openrouter: "OpenRouter",
          evon: "Evon",
        };
        const provider = providerLabel[msg.llm_provider] || msg.llm_provider || "LLM";
        els.modeBadge.textContent = `Live · Gnani + ${provider}`;
      } else if (mode === "speech_only") {
        els.modeBadge.hidden = false;
        els.modeBadge.textContent = "Speech on · mock brain";
      } else {
        els.modeBadge.hidden = false;
        els.modeBadge.textContent = "Demo mode";
      }
      if (msg.ai_disclosure) els.aiDisclosure.textContent = msg.ai_disclosure;
      sessionActive = true;
      syncConversationControls();
      setState("Listening", "listening");
      setCaption("Tap the microphone when you’re ready, or type below.");
      showError("");
      els.talk.disabled = false;
      els.mute.disabled = false;
      if (document.activeElement === els.start) els.talk.focus();
      return;
    }
    if (msg.type === "audio_chunk") {
      turnAudioHandled = true;
      setState("Speaking…", "speaking");
      enqueueAudio(msg.audio_base64, msg.audio_content_type);
      if (msg.text) setCaption(msg.text);
      return;
    }
    if (msg.type === "turn") {
      handleTurnMessage(msg);
      return;
    }
    if (msg.type === "language" || msg.type === "consent") return;
    if (msg.type === "closed") {
      endSessionLocal(false);
      return;
    }
    if (msg.type === "error") {
      showError(
        msg.detail
          ? `${msg.code}: ${msg.detail}`
          : `Something went wrong (${msg.code || "unknown"}). You can try again.`,
      );
      if (sessionActive) setState("Listening", "listening");
    }
  });
  ws.addEventListener("close", () => {
    if (socket !== ws) return;
    const wasActive = sessionActive;
    sessionActive = false;
    syncConversationControls();
    setState(wasActive ? "Connection lost" : "Conversation ended", wasActive ? "reconnecting" : "idle");
    setCaption(wasActive ? "Start again to reconnect. Your conversation is shown below." : "You can start a new conversation whenever you’re ready.");
    els.sendText.disabled = true;
    els.stop.disabled = true;
    els.talk.disabled = true;
    els.mute.disabled = true;
    els.start.disabled = false;
    stopMicCapture();
    stopSpeaking();
    socket = null;
  });
}

async function ensureMic() {
  const constraints = {
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      ...(selectedMicId ? { deviceId: { exact: selectedMicId } } : {}),
    },
  };
  try {
    if (micStream) {
      for (const track of micStream.getTracks()) track.stop();
      micStream = null;
    }
    micStream = await navigator.mediaDevices.getUserMedia(constraints);
    await refreshDevices();
    els.micSelect.disabled = false;
    els.speakerSelect.disabled = false;
    els.refreshDevices.disabled = false;
    els.testSpeaker.disabled = false;
    return micStream;
  } catch (err) {
    const name = err instanceof Error ? err.name : "";
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      throw new Error(
        "Microphone access was blocked. Allow the mic in your browser settings, or type a message instead.",
      );
    }
    if (selectedMicId) {
      selectedMicId = "";
      localStorage.removeItem(STORAGE_MIC);
      els.micSelect.value = "";
      return ensureMic();
    }
    throw new Error("We could not use your microphone. You can still type a message.");
  }
}

function floatTo16BitPCM(float32Array) {
  const out = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function mergePcmChunks(chunks) {
  const total = chunks.reduce((sum, c) => sum + c.length, 0);
  const merged = new Int16Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

async function startRecording() {
  if (!sessionActive || isRecording) return;
  const attempt = ++recordingAttempt;
  stopSpeaking();
  await ensurePlaybackUnlocked();
  if (!sessionActive || attempt !== recordingAttempt) return;
  const stream = await ensureMic();
  if (!sessionActive || attempt !== recordingAttempt) {
    for (const track of stream.getTracks()) track.stop();
    return;
  }
  pcmChunks = [];
  micAudioContext = new AudioContext();
  const nativeRate = micAudioContext.sampleRate;
  micSource = micAudioContext.createMediaStreamSource(stream);
  micProcessor = micAudioContext.createScriptProcessor(4096, 1, 1);
  micSilentGain = micAudioContext.createGain();
  micSilentGain.gain.value = 0;
  micProcessor.onaudioprocess = (event) => {
    if (!isRecording) return;
    const input = event.inputBuffer.getChannelData(0);
    let samples = input;
    if (nativeRate !== PCM_SAMPLE_RATE) {
      const ratio = nativeRate / PCM_SAMPLE_RATE;
      const outLen = Math.floor(input.length / ratio);
      const resampled = new Float32Array(outLen);
      for (let i = 0; i < outLen; i++) {
        resampled[i] = input[Math.floor(i * ratio)];
      }
      samples = resampled;
    }
    pcmChunks.push(floatTo16BitPCM(samples));
  };
  // Keep processor alive without sending mic to speakers (was causing echo / confusion).
  micSource.connect(micProcessor);
  micProcessor.connect(micSilentGain);
  micSilentGain.connect(micAudioContext.destination);
  isRecording = true;
  els.talk.setAttribute("aria-pressed", "true");
  document.getElementById("talkLabel").textContent = "Send voice";
  setState("Listening to you", "listening");
  setCaption("Take your time. Tap Send voice when you’re finished.");
}

function stopMicCapture() {
  recordingAttempt++;
  isRecording = false;
  els.talk.setAttribute("aria-pressed", "false");
  document.getElementById("talkLabel").textContent = "Tap to talk";
  if (micStream) {
    for (const track of micStream.getTracks()) track.stop();
    micStream = null;
  }
  pcmChunks = [];
  if (micProcessor) {
    micProcessor.disconnect();
    micProcessor.onaudioprocess = null;
    micProcessor = null;
  }
  if (micSilentGain) {
    micSilentGain.disconnect();
    micSilentGain = null;
  }
  if (micSource) {
    micSource.disconnect();
    micSource = null;
  }
  if (micAudioContext) {
    void micAudioContext.close();
    micAudioContext = null;
  }
}

function stopRecordingAndSend() {
  if (!isRecording) return;
  isRecording = false;
  const pcm = mergePcmChunks(pcmChunks);
  pcmChunks = [];
  stopMicCapture();
  if (pcm.length < PCM_SAMPLE_RATE / 8) {
    if (sessionActive) setState("Listening", "listening");
    setCaption("That was too short. Tap to talk again, or type your message.");
    return;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  const pcmBase64 = btoa(binary);
  setState("Processing…", "processing");
  setCaption("Understanding what you said…");
  sendJson({ type: "audio", pcm_base64: pcmBase64 });
}

function endSessionLocal(sendClose = true) {
  sessionActive = false;
  syncConversationControls();
  stopMicCapture();
  stopSpeaking();
  if (micStream) {
    for (const track of micStream.getTracks()) track.stop();
    micStream = null;
  }
  if (sendClose && socket?.readyState === WebSocket.OPEN) {
    sendJson({ type: "close" });
    socket.close();
  }
  els.sendText.disabled = true;
  els.stop.disabled = true;
  els.talk.disabled = true;
  els.mute.disabled = true;
  els.start.disabled = false;
  setState("Conversation ended", "idle");
  setCaption("You can start a new conversation whenever you’re ready.");
  els.start.focus();
}

els.start.addEventListener("click", async () => {
  showError("");
  els.start.disabled = true;
  document.getElementById("startLabel").textContent = "Connecting…";
  setState("Connecting…", "processing");
  setCaption("");
  try {
    await ensurePlaybackUnlocked();
    const isUuid = /^[0-9a-f-]{36}$/i.test(clinicParam);
    const payload = {
      language: els.language.value,
      recording_consent: els.consent.checked,
      ...(isUuid ? { clinic_id: clinicParam } : { clinic_slug: clinicParam }),
    };
    if (clinicMeta?.id && !isUuid) {
      payload.clinic_id = clinicMeta.id;
      delete payload.clinic_slug;
    }
    const res = await fetch(`${API_BASE}/v1/visitor/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body?.detail?.message || body?.detail || `Could not start (${res.status})`);
    }
    visitorToken = body.visitor_token;
    if (body.clinic_name) els.clinicName.textContent = body.clinic_name;
    if (body.ai_disclosure) els.aiDisclosure.textContent = body.ai_disclosure;
    const ws = await connectSocket(body.ws_path, visitorToken);
    bindSocket(ws);
    els.sendText.disabled = false;
    els.stop.disabled = false;
    els.testSpeaker.disabled = false;
    els.refreshDevices.disabled = false;
    els.micSelect.disabled = false;
    els.speakerSelect.disabled = false;
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
    els.start.disabled = false;
    document.getElementById("startLabel").textContent = "Try again";
  }
});

function sendTextTurn(text) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const trimmed = text.trim();
  if (!trimmed) return;
  stopMicCapture();
  stopSpeaking();
  void ensurePlaybackUnlocked();
  setState("Processing…", "processing");
  setCaption(`You: ${trimmed}`);
  sendJson({ type: "text", text: trimmed });
}

els.sendText.addEventListener("click", () => {
  sendTextTurn(els.textInput.value);
  els.textInput.value = "";
});

els.textInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!els.sendText.disabled) els.sendText.click();
  }
});

els.stop.addEventListener("click", () => {
  if (!socket) return;
  endSessionLocal(true);
});

els.language.addEventListener("change", () => syncLanguage());
els.consent.addEventListener("change", () => syncConsent());

els.mute.addEventListener("click", () => {
  outputMuted = !outputMuted;
  document.getElementById("muteLabel").textContent = outputMuted ? "Sound off" : "Sound on";
  els.mute.setAttribute("aria-label", outputMuted ? "Unmute receptionist" : "Mute receptionist");
  els.mute.setAttribute("aria-pressed", outputMuted ? "true" : "false");
  if (outputMuted) {
    stopSpeaking();
  }
  setState(isRecording ? "Listening to you" : "Ready for your next question", isRecording ? "listening" : "ready");
  setCaption(outputMuted ? "Sound is off. You can still read replies below." : "Sound is on. You’ll hear the receptionist’s replies.");
});

els.micSelect.addEventListener("change", () => {
  selectedMicId = els.micSelect.value;
  if (selectedMicId) localStorage.setItem(STORAGE_MIC, selectedMicId);
  else localStorage.removeItem(STORAGE_MIC);
  if (isRecording || els.talk.disabled && sessionActive) {
    stopMicCapture();
    setState("Ready for your next question", "ready");
    setCaption("Microphone changed. Tap to talk to start a new recording.");
  }
});

els.speakerSelect.addEventListener("change", () => {
  selectedSpeakerId = els.speakerSelect.value;
  if (selectedSpeakerId) localStorage.setItem(STORAGE_SPEAKER, selectedSpeakerId);
  else localStorage.removeItem(STORAGE_SPEAKER);
  if (playbackCtx && typeof playbackCtx.setSinkId === "function") {
    void playbackCtx.setSinkId(selectedSpeakerId || "").catch((err) => {
      console.warn("AudioContext.setSinkId failed", err);
    });
  }
});

els.refreshDevices.addEventListener("click", () => {
  void refreshDevices().catch(() => showError("Could not refresh audio devices. Check your browser permissions and try again."));
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    els.textInput.value = button.dataset.prompt;
    els.textInput.focus();
    document.getElementById("messageHint").textContent = sessionActive
      ? "Your message is ready. Edit it or press Send."
      : "Your message is ready. Start a conversation to send it.";
  });
});

els.testSpeaker.addEventListener("click", () => {
  void playTestTone();
});

els.talk.addEventListener("click", async () => {
  if (!sessionActive || els.talk.disabled) return;
  if (isRecording) {
    stopRecordingAndSend();
    return;
  }
  els.talk.disabled = true;
  document.getElementById("talkLabel").textContent = "Opening mic…";
  showError("");
  setCaption("Allow microphone access if your browser asks.");
  try {
    await startRecording();
  } catch (err) {
    stopMicCapture();
    showError(err instanceof Error ? err.message : String(err));
    setCaption("You can still type a message below.");
  } finally {
    els.talk.disabled = !sessionActive;
    if (!isRecording) document.getElementById("talkLabel").textContent = "Tap to talk";
  }
});

if (navigator.mediaDevices?.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", () => {
    void refreshDevices();
  });
}

void loadClinic();
void refreshDevices();
