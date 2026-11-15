from __future__ import annotations

import asyncio
import io
import struct
import wave
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from app.core.config import Settings


@dataclass
class TranscriptEvent:
    text: str
    is_final: bool = True


@dataclass
class TtsAudio:
    pcm_bytes: bytes
    sample_rate: int = 16000
    content_type: str = "audio/pcm"


class SttClient(Protocol):
    async def transcribe_pcm(
        self, pcm: bytes, *, language: str, sample_rate: int = 16000
    ) -> TranscriptEvent: ...


class TtsClient(Protocol):
    async def synthesize(self, text: str, *, language: str) -> TtsAudio: ...


class MockSttClient:
    def __init__(self, text: str = "What services do you offer?"):
        self.text = text
        self.calls = 0

    async def transcribe_pcm(
        self, pcm: bytes, *, language: str, sample_rate: int = 16000
    ) -> TranscriptEvent:
        self.calls += 1
        _ = (pcm, language, sample_rate)
        return TranscriptEvent(text=self.text, is_final=True)


class MockTtsClient:
    def __init__(self):
        self.calls = 0
        self.last_text: Optional[str] = None

    async def synthesize(self, text: str, *, language: str) -> TtsAudio:
        self.calls += 1
        self.last_text = text
        # Tiny silent PCM placeholder (not a real recording).
        return TtsAudio(pcm_bytes=b"\x00\x00" * 160, sample_rate=16000)


def _pcm16_mono_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _wav_sample_rate(audio: bytes, default: int = 16000) -> int:
    if len(audio) < 44 or audio[0:4] != b"RIFF":
        return default
    try:
        return struct.unpack_from("<I", audio, 24)[0]
    except struct.error:
        return default


class GnaniSttAdapter:
    """Gnani STT: prefer SDK stream; fall back to REST file transcription."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe_pcm(
        self, pcm: bytes, *, language: str, sample_rate: int = 16000
    ) -> TranscriptEvent:
        if not self.settings.gnani_configured:
            raise RuntimeError("gnani_not_configured")
        if not pcm:
            return TranscriptEvent(text="", is_final=True)

        try:
            return await self._transcribe_sdk(pcm, language=language, sample_rate=sample_rate)
        except Exception:
            return await self._transcribe_rest(pcm, language=language, sample_rate=sample_rate)

    async def _transcribe_sdk(
        self, pcm: bytes, *, language: str, sample_rate: int
    ) -> TranscriptEvent:
        # Import can fail on Python <3.10 (gnani uses `str | None`).
        from gnani.stt import GnaniSTTStreamClient, StreamTranscriptEvent  # type: ignore

        texts: list[str] = []
        kwargs = {
            "api_key": self.settings.gnani_api_key,
            "language_code": language,
            "sample_rate": sample_rate,
            "base_url": self.settings.gnani_api_base_url,
        }
        # model is optional on older SDK builds
        try:
            stream_cm = GnaniSTTStreamClient(
                **kwargs, model=self.settings.gnani_stt_model
            )
        except TypeError:
            stream_cm = GnaniSTTStreamClient(**kwargs)

        async with stream_cm as stream:
            frame = max(sample_rate // 30 * 2, 640)
            for i in range(0, len(pcm), frame):
                await stream.send_audio(pcm[i : i + frame])
            async for event in stream:
                if isinstance(event, StreamTranscriptEvent) and event.text:
                    texts.append(event.text)
        return TranscriptEvent(text=" ".join(texts).strip(), is_final=True)

    async def _transcribe_rest(
        self, pcm: bytes, *, language: str, sample_rate: int
    ) -> TranscriptEvent:
        wav_bytes = _pcm16_mono_to_wav(pcm, sample_rate)
        base = self.settings.gnani_api_base_url.rstrip("/")
        url = f"{base}/stt/v3"
        headers = {"X-API-Key-ID": self.settings.gnani_api_key}
        data = {
            "model": self.settings.gnani_stt_model,
            "language_code": language,
        }
        files = {"audio_file": ("utterance.wav", wav_bytes, "audio/wav")}
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(url, headers=headers, data=data, files=files)
        if response.status_code >= 400:
            raise RuntimeError(f"gnani_stt_http_{response.status_code}")
        body = response.json()
        transcript = str(body.get("transcript") or "").strip()
        return TranscriptEvent(text=transcript, is_final=True)


class GnaniTtsAdapter:
    """Gnani TTS: prefer SDK REST; fall back to HTTP when SDK cannot import."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _voice_for(self, language: str) -> str:
        if language.startswith("hi"):
            return self.settings.gnani_tts_voice_hi
        if language.startswith("te"):
            return self.settings.gnani_tts_voice_te
        return self.settings.gnani_tts_voice_en

    async def synthesize(self, text: str, *, language: str) -> TtsAudio:
        if not self.settings.gnani_configured:
            raise RuntimeError("gnani_not_configured")
        try:
            return await self._synthesize_sdk(text, language=language)
        except Exception:
            return await self._synthesize_rest(text, language=language)

    async def _synthesize_sdk(self, text: str, *, language: str) -> TtsAudio:
        from gnani.tts import AudioConfig, GnaniTTSClient  # type: ignore

        def _run() -> bytes:
            client = GnaniTTSClient(
                api_key=self.settings.gnani_api_key,
                base_url=self.settings.gnani_api_base_url,
            )
            audio = client.synthesize(
                text,
                voice=self._voice_for(language),
                model=self.settings.gnani_tts_model,
                language=language,
                audio_config=AudioConfig(
                    sample_rate=16000,
                    encoding="linear_pcm",
                    container="wav",
                ),
            )
            return bytes(audio) if not isinstance(audio, bytes) else audio

        audio = await asyncio.to_thread(_run)
        return TtsAudio(
            pcm_bytes=audio,
            sample_rate=_wav_sample_rate(audio, 16000),
            content_type="audio/wav",
        )

    async def _synthesize_rest(self, text: str, *, language: str) -> TtsAudio:
        base = self.settings.gnani_api_base_url.rstrip("/")
        url = f"{base}/api/v1/tts/inference"
        headers = {
            "X-API-Key-ID": self.settings.gnani_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "voice": self._voice_for(language),
            "model": self.settings.gnani_tts_model,
            "language": language,
            "speed": 1.0,
            "audio_config": {
                "sample_rate": 16000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(
                f"gnani_tts_http_{response.status_code}:{response.text[:200]}"
            )
        audio = response.content
        return TtsAudio(
            pcm_bytes=audio,
            sample_rate=_wav_sample_rate(audio, 16000),
            content_type="audio/wav",
        )


def build_stt_client(settings: Settings, *, force_mock: bool = False) -> SttClient:
    if force_mock or not settings.gnani_configured:
        return MockSttClient()
    return GnaniSttAdapter(settings)


def build_tts_client(settings: Settings, *, force_mock: bool = False) -> TtsClient:
    if force_mock or not settings.gnani_configured:
        return MockTtsClient()
    return GnaniTtsAdapter(settings)
