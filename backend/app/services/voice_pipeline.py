from __future__ import annotations

import io
import json
import re
import wave
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from app.services.clinic_knowledge import clinic_knowledge_prompt_block
from app.services.clinic_store import ClinicStore
from app.services.gnani_speech import SttClient, TtsAudio, TtsClient
from app.services.llm_evon import LlmClient, LlmTurn
from app.services.voice_tools import execute_tool, refuses_medical_advice

MAX_TOOL_ROUNDS = 3
MAX_HISTORY_MESSAGES = 8
AudioChunkCallback = Callable[[int, str, TtsAudio], Awaitable[None]]


@dataclass
class VoiceTurnResult:
    user_text: str
    assistant_text: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    audio: Optional[TtsAudio] = None
    escalated: bool = False
    refused_medical: bool = False
    llm_failed: bool = False
    booking_confirmed: bool = False
    language: str = "en-IN"
    latency_ms: Optional[Dict[str, int]] = None


def _booking_announcement_allowed(tool_results: List[Dict[str, Any]]) -> bool:
    for item in tool_results:
        if item.get("tool") != "create_appointment":
            continue
        if not item.get("accepted"):
            return False
        result = item.get("result") or {}
        if result.get("appointment_id") and result.get("status") in {"booked", "rescheduled"}:
            return True
    return False


def _sanitize_spoken_text(text: str, tool_results: List[Dict[str, Any]]) -> str:
    lowered = text.lower()
    failed_create = any(
        item.get("tool") == "create_appointment" and not item.get("accepted")
        for item in tool_results
    )
    pending_create = any(
        item.get("tool") == "create_appointment"
        and item.get("accepted")
        and (item.get("result") or {}).get("status") == "pending"
        for item in tool_results
    )
    success_phrases = (
        "appointment is confirmed",
        "booking is confirmed",
        "successfully booked",
        "your appointment is booked",
        "i've booked",
        "i have booked",
    )
    if (failed_create or pending_create) and any(p in lowered for p in success_phrases):
        if pending_create:
            return (
                "I'm an AI receptionist. That booking is pending while we confirm "
                "availability with the calendar provider. A team member will follow up if needed."
            )
        reason = next(
            (
                (item.get("reason") or (item.get("result") or {}).get("error") or "unavailable")
                for item in tool_results
                if item.get("tool") == "create_appointment" and not item.get("accepted")
            ),
            "unavailable",
        )
        return (
            "I'm an AI receptionist. I could not confirm that booking "
            f"({reason.replace('_', ' ')}). I can offer another time or escalate to staff."
        )
    return text


def trim_history(
    history: Optional[List[Dict[str, Any]]], *, max_messages: int = MAX_HISTORY_MESSAGES
) -> List[Dict[str, Any]]:
    if not history:
        return []
    return list(history)[-max_messages:]


def split_spoken_sentences(text: str) -> List[str]:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?।])\s+", cleaned)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences or [cleaned]


def _wav_pcm_frames(audio: bytes) -> tuple[bytes, int]:
    if len(audio) >= 44 and audio[0:4] == b"RIFF":
        with wave.open(io.BytesIO(audio), "rb") as wav:
            return wav.readframes(wav.getnframes()), wav.getframerate()
    return audio, 16000


def merge_tts_audio(parts: List[TtsAudio]) -> Optional[TtsAudio]:
    if not parts:
        return None
    pcm_chunks: List[bytes] = []
    sample_rate = parts[0].sample_rate or 16000
    content_type = parts[0].content_type or "audio/pcm"
    for part in parts:
        frames, rate = _wav_pcm_frames(part.pcm_bytes)
        sample_rate = rate or sample_rate
        pcm_chunks.append(frames)
        if part.content_type:
            content_type = part.content_type
    merged = b"".join(pcm_chunks)
    if content_type == "audio/wav" or (
        len(parts[0].pcm_bytes) >= 44 and parts[0].pcm_bytes[0:4] == b"RIFF"
    ):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(merged)
        return TtsAudio(pcm_bytes=buffer.getvalue(), sample_rate=sample_rate, content_type="audio/wav")
    return TtsAudio(pcm_bytes=merged, sample_rate=sample_rate, content_type=content_type)


async def synthesize_progressive(
    tts: TtsClient,
    text: str,
    *,
    language: str,
    on_audio_chunk: Optional[AudioChunkCallback] = None,
) -> Optional[TtsAudio]:
    """Synthesize sentence-by-sentence so the first audio can play early."""
    sentences = split_spoken_sentences(text)
    if not sentences:
        return None
    parts: List[TtsAudio] = []
    for index, sentence in enumerate(sentences):
        part = await tts.synthesize(sentence, language=language)
        parts.append(part)
        if on_audio_chunk is not None:
            await on_audio_chunk(index, sentence, part)
    return merge_tts_audio(parts)


def _execute_tool_calls(
    store: ClinicStore,
    *,
    clinic_id: UUID,
    voice_session_id: UUID,
    tool_calls: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
) -> bool:
    """Execute tool calls, append tool messages. Returns True if any escalate succeeded."""
    escalated = False
    for call in tool_calls:
        function = call.get("function") or {}
        name = str(function.get("name") or "")
        raw_args = function.get("arguments") or "{}"
        call_id = str(call.get("id") or name)
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except json.JSONDecodeError:
            args = {}
        accepted, result, reason = execute_tool(
            store,
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name=name,
            arguments=args,
        )
        tool_results.append(
            {"tool": name, "accepted": accepted, "result": result, "reason": reason}
        )
        if name == "escalate" and accepted:
            escalated = True
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(
                    {"accepted": accepted, "result": result, "reason": reason}
                ),
            }
        )
    return escalated


async def run_voice_turn(
    store: ClinicStore,
    *,
    clinic_id: UUID,
    voice_session_id: UUID,
    language: str,
    pcm: bytes,
    stt: SttClient,
    tts: TtsClient,
    llm: LlmClient,
    history: Optional[List[Dict[str, Any]]] = None,
    recording_consent: bool = False,
    user_text_override: Optional[str] = None,
    on_audio_chunk: Optional[AudioChunkCallback] = None,
) -> VoiceTurnResult:
    """STT/text → policy → bounded LLM↔tools loop → progressive TTS.

    Tool results are fed back into the model before the spoken answer is finalized.
    Booking confirmation requires an accepted create_appointment with appointment_id.
    """
    import time

    _ = recording_consent
    t0 = time.perf_counter()
    timing: Dict[str, int] = {}

    if user_text_override is not None:
        user_text = user_text_override.strip()
    else:
        transcript = await stt.transcribe_pcm(pcm, language=language)
        user_text = (transcript.text or "").strip()
    timing["stt_ms"] = int((time.perf_counter() - t0) * 1000)

    if not user_text:
        spoken = "I didn't catch that. Could you please repeat?"
        audio = await synthesize_progressive(
            tts, spoken, language=language, on_audio_chunk=on_audio_chunk
        )
        return VoiceTurnResult(
            user_text="",
            assistant_text=spoken,
            audio=audio,
            language=language,
            latency_ms=timing,
        )

    if refuses_medical_advice(user_text):
        accepted, result, _reason = execute_tool(
            store,
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name="escalate",
            arguments={
                "reason": "medical_advice_request",
                "summary": user_text[:500],
            },
        )
        spoken = (
            "I'm an AI receptionist and I can't diagnose or recommend treatment. "
            "I've asked a team member to follow up with you."
        )
        t_tts = time.perf_counter()
        audio = await synthesize_progressive(
            tts, spoken, language=language, on_audio_chunk=on_audio_chunk
        )
        timing["tts_ms"] = int((time.perf_counter() - t_tts) * 1000)
        timing["total_ms"] = int((time.perf_counter() - t0) * 1000)
        return VoiceTurnResult(
            user_text=user_text,
            assistant_text=spoken,
            tool_results=[{"tool": "escalate", "accepted": accepted, "result": result}],
            audio=audio,
            escalated=accepted,
            refused_medical=True,
            language=language,
            latency_ms=timing,
        )

    clinic_context = clinic_knowledge_prompt_block(store, clinic_id)
    messages: List[Dict[str, Any]] = trim_history(history)
    messages.append({"role": "user", "content": user_text})

    tool_results: List[Dict[str, Any]] = []
    escalated = False
    assistant_text = ""

    t_llm = time.perf_counter()
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            turn: LlmTurn = await llm.complete(
                messages=messages, language=language, clinic_context=clinic_context
            )
            if not turn.tool_calls:
                assistant_text = turn.assistant_text
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": turn.assistant_text or None,
                    "tool_calls": turn.tool_calls,
                }
            )
            if _execute_tool_calls(
                store,
                clinic_id=clinic_id,
                voice_session_id=voice_session_id,
                tool_calls=turn.tool_calls,
                messages=messages,
                tool_results=tool_results,
            ):
                escalated = True
        else:
            # Exhausted rounds with tools — ask once more for a closing reply without tools.
            closing = await llm.complete(
                messages=messages, language=language, clinic_context=clinic_context
            )
            assistant_text = closing.assistant_text
    except Exception:
        timing["llm_ms"] = int((time.perf_counter() - t_llm) * 1000)
        accepted, result, _reason = execute_tool(
            store,
            clinic_id=clinic_id,
            voice_session_id=voice_session_id,
            tool_name="escalate",
            arguments={
                "reason": "llm_unreachable",
                "summary": f"Caller said: {user_text[:400]}",
            },
        )
        spoken = (
            "I'm having trouble reaching the AI brain right now. "
            "I've notified the clinic team to help you."
        )
        t_tts = time.perf_counter()
        audio = await synthesize_progressive(
            tts, spoken, language=language, on_audio_chunk=on_audio_chunk
        )
        timing["tts_ms"] = int((time.perf_counter() - t_tts) * 1000)
        timing["total_ms"] = int((time.perf_counter() - t0) * 1000)
        return VoiceTurnResult(
            user_text=user_text,
            assistant_text=spoken,
            tool_results=[{"tool": "escalate", "accepted": accepted, "result": result}],
            audio=audio,
            escalated=accepted,
            llm_failed=True,
            language=language,
            latency_ms=timing,
        )
    timing["llm_ms"] = int((time.perf_counter() - t_llm) * 1000)

    if not assistant_text:
        if escalated:
            assistant_text = "I've asked a team member to help you further."
        elif tool_results:
            assistant_text = "I've checked that for you."
        else:
            assistant_text = "I'm Rhea, an AI receptionist. How can I help with booking?"

    assistant_text = _sanitize_spoken_text(assistant_text, tool_results)
    if "ai" not in assistant_text.lower() and "artificial" not in assistant_text.lower():
        assistant_text = f"I'm an AI receptionist. {assistant_text}"

    booking_confirmed = _booking_announcement_allowed(tool_results)
    t_tts = time.perf_counter()
    audio = await synthesize_progressive(
        tts, assistant_text, language=language, on_audio_chunk=on_audio_chunk
    )
    timing["tts_ms"] = int((time.perf_counter() - t_tts) * 1000)
    timing["total_ms"] = int((time.perf_counter() - t0) * 1000)
    return VoiceTurnResult(
        user_text=user_text,
        assistant_text=assistant_text,
        tool_results=tool_results,
        audio=audio,
        escalated=escalated,
        booking_confirmed=booking_confirmed,
        language=language,
        latency_ms=timing,
    )
