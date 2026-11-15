import { pipeline, env } from "@xenova/transformers";
import { pathToFileURL } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs/promises";
import { existsSync } from "node:fs";

// Node/Electron main has no browser Cache API
env.allowLocalModels = false;
env.useBrowserCache = false;
// Keep downloaded models usable after the application rename.
const legacyCache = path.join(os.homedir(), ".cache", "whisper-flow");
env.cacheDir = existsSync(legacyCache)
  ? legacyCache
  : path.join(os.homedir(), ".cache", "lala-dictation");

let asr = null;

async function getAsr(onProgress) {
  if (asr) return asr;
  asr = await pipeline("automatic-speech-recognition", "Xenova/whisper-tiny.en", {
    quantized: true,
    progress_callback: onProgress,
  });
  return asr;
}

/**
 * @param {ArrayBuffer|Buffer|Uint8Array} wavBuf 16kHz mono PCM WAV from renderer
 */
export async function transcribeWebm(wavBuf, { onProgress } = {}) {
  if (!wavBuf?.byteLength && !wavBuf?.length) return "";

  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "lala-dictation-"));
  const wavPath = path.join(dir, "clip.wav");
  await fs.writeFile(wavPath, Buffer.from(wavBuf));

  try {
    const model = await getAsr(onProgress);
    const result = await model(pathToFileURL(wavPath).href, {
      language: "english",
      task: "transcribe",
      chunk_length_s: 30,
    });
    return (result?.text || "").trim();
  } finally {
    await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

export async function warmAsr(onProgress) {
  await getAsr(onProgress);
}
