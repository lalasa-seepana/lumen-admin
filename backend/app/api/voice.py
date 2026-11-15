from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import CurrentUser, SettingsDep, StoreDep
from app.core.config import get_settings
from app.models.voice import HandoverOut, VoiceSessionCreate, VoiceSessionOut
from app.services import clinics as clinic_service
from app.services import conversations as conversation_service
from app.services.gnani_speech import MockSttClient, MockTtsClient, build_stt_client, build_tts_client
from app.services.llm_evon import EvonOpenAIClient, MockLlmClient
from app.services.voice_pipeline import run_voice_turn
from app.services.voice_tools import CONSENT_TEXT_VERSION

router = APIRouter(prefix="/v1/voice", tags=["voice"])


@router.get("/status")
def voice_status(settings: SettingsDep) -> Dict[str, Any]:
    speech_live = settings.gnani_configured
    ready_for_live = speech_live and settings.llm_configured
    if ready_for_live:
        mode = "configured"
    elif speech_live:
        # Speak with Gnani; reason with Mock LLM until OpenAI/Evon is configured.
        mode = "speech_only"
    elif settings.llm_configured:
        mode = "llm_only"
    else:
        mode = "demo"
    return {
        "mode": mode,
        "ready_for_live": ready_for_live,
        "speech_live": speech_live,
        "gnani_configured": settings.gnani_configured,
        "llm_configured": settings.llm_configured,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "evon_hf_repo_id": settings.evon_hf_repo_id,
        "blockers": _blockers(settings),
        "languages": ["en-IN", "hi-IN", "te-IN"],
        "noise_notes": {
            "browser": "Enable echoCancellation and noiseSuppression on getUserMedia when supported.",
            "gnani_vad": "Use provider language_code + streaming VAD via gnani-vachana when live.",
            "gnani_noise_cancellation": (
                "Dedicated Gnani noise-cancellation parameters are not documented in this "
                "integration; do not invent API fields. Browser AEC/NS is the verified fallback."
            ),
        },
    }


def _blockers(settings) -> List[str]:
    blockers: List[str] = []
    if not settings.gnani_configured:
        blockers.append("GNANI_API_KEY (D03)")
    if not settings.llm_configured:
        if settings.llm_base_url.strip() and settings.llm_provider == "openai":
            blockers.append("LLM_API_KEY (OpenAI secret key required for api.openai.com)")
        else:
            blockers.append(
                "LLM_BASE_URL + LLM_API_KEY (OpenAI recommended) — "
                "or leave empty for mock brain + Gnani speech"
            )
    return blockers


@router.post("/sessions", response_model=VoiceSessionOut, status_code=status.HTTP_201_CREATED)
def create_voice_session(
    body: VoiceSessionCreate, user: CurrentUser, store: StoreDep, settings: SettingsDep
) -> VoiceSessionOut:
    clinic, _ = clinic_service.require_membership(store, user.id)
    session = store.create_voice_session(
        clinic_id=clinic.id,
        language=body.language,
        recording_consent=body.recording_consent,
        actor_type="owner",
        consent_version=CONSENT_TEXT_VERSION if body.recording_consent else None,
    )
    conversation_service.ensure_conversation_for_session(
        store, settings, voice_session_id=session.id
    )
    return VoiceSessionOut(
        id=session.id,
        clinic_id=session.clinic_id,
        language=session.language,
        recording_consent=session.recording_consent,
        status=session.status,
        created_at=session.created_at,
        visitor_token=session.visitor_token,
        ws_path=f"/v1/voice/ws/{session.id}",
    )


@router.get("/handovers", response_model=List[HandoverOut])
def list_handovers(user: CurrentUser, store: StoreDep) -> List[HandoverOut]:
    """Compatibility alias — prefer GET /v1/handovers (Epic 7)."""
    return conversation_service.list_handovers(store, user_id=user.id)


@router.websocket("/ws/{session_id}")
async def voice_ws(
    websocket: WebSocket,
    session_id: UUID,
    store: StoreDep,
    token: str = Query(default=""),
):
    settings = get_settings()
    await websocket.accept()
    session = store.get_voice_session(session_id)
    if session is None or session.status != "open":
        await websocket.send_json({"type": "error", "code": "session_not_found"})
        await websocket.close(code=4404)
        return
    if not token or token != (session.visitor_token or ""):
        await websocket.send_json({"type": "error", "code": "invalid_session_token"})
        await websocket.close(code=4401)
        return

    # Speech (Gnani) and brain (OpenAI / Evon) are independent.
    speech_live = settings.gnani_configured
    live = speech_live and settings.llm_configured
    stt = build_stt_client(settings, force_mock=not speech_live)
    tts = build_tts_client(settings, force_mock=not speech_live)
    llm = EvonOpenAIClient(settings) if settings.llm_configured else MockLlmClient()
    if not settings.gnani_configured:
        stt = MockSttClient()
        tts = MockTtsClient()

    language = session.language
    recording_consent = session.recording_consent

    if live:
        mode = "live"
    elif speech_live:
        mode = "speech_only"
    else:
        mode = "mock"

    await websocket.send_json(
        {
            "type": "ready",
            "session_id": str(session.id),
            "clinic_id": str(session.clinic_id),
            "language": language,
            "mode": mode,
            "ready_for_live": live,
            "speech_live": speech_live,
            "gnani_configured": settings.gnani_configured,
            "llm_configured": settings.llm_configured,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "blockers": _blockers(settings),
            "ai_disclosure": "You are chatting with Rhea, an AI receptionist, not a clinician.",
            "recording_consent": recording_consent,
        }
    )

    history: List[Dict[str, Any]] = []
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            payload: Dict[str, Any]
            if "text" in message and message["text"] is not None:
                payload = json.loads(message["text"])
            elif "bytes" in message and message["bytes"] is not None:
                session = store.get_voice_session(session_id) or session
                language = session.language
                recording_consent = session.recording_consent
                result = await run_voice_turn(
                    store,
                    clinic_id=session.clinic_id,
                    voice_session_id=session.id,
                    language=language,
                    pcm=message["bytes"],
                    stt=stt,
                    tts=tts,
                    llm=llm,
                    history=history,
                    recording_consent=recording_consent,
                    on_audio_chunk=_chunk_sender(websocket),
                )
                _after_turn(store, settings, session.id, result)
                await _send_turn(websocket, result)
                if result.user_text:
                    history.append({"role": "user", "content": result.user_text})
                    history.append({"role": "assistant", "content": result.assistant_text})
                    if len(history) > 16:
                        del history[:-16]
                continue
            else:
                continue

            msg_type = payload.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if msg_type == "set_language":
                lang = str(payload.get("language") or "").strip()
                if lang not in {"en-IN", "hi-IN", "te-IN"}:
                    await websocket.send_json({"type": "error", "code": "invalid_language"})
                    continue
                session = store.update_voice_session(session_id, language=lang)
                language = lang
                await websocket.send_json({"type": "language", "language": language})
                continue
            if msg_type == "set_consent":
                consent = bool(payload.get("recording_consent"))
                fields: Dict[str, Any] = {"recording_consent": consent}
                if consent:
                    fields["consent_version"] = CONSENT_TEXT_VERSION
                    fields["consent_recorded_at"] = datetime.now(timezone.utc)
                session = store.update_voice_session(session_id, **fields)
                recording_consent = consent
                # Keep conversation row in sync for retention gating.
                conversation_service.sync_session_consent(
                    store, settings, voice_session_id=session_id, recording_consent=consent
                )
                await websocket.send_json(
                    {
                        "type": "consent",
                        "recording_consent": consent,
                        "consent_version": session.consent_version,
                    }
                )
                continue
            if msg_type == "text":
                session = store.get_voice_session(session_id) or session
                language = session.language
                recording_consent = session.recording_consent
                text = str(payload.get("text") or "")
                result = await run_voice_turn(
                    store,
                    clinic_id=session.clinic_id,
                    voice_session_id=session.id,
                    language=language,
                    pcm=b"",
                    stt=stt,
                    tts=tts,
                    llm=llm,
                    history=history,
                    recording_consent=recording_consent,
                    user_text_override=text,
                    on_audio_chunk=_chunk_sender(websocket),
                )
                _after_turn(store, settings, session.id, result)
                await _send_turn(websocket, result)
                if result.user_text:
                    history.append({"role": "user", "content": result.user_text})
                    history.append({"role": "assistant", "content": result.assistant_text})
                    if len(history) > 16:
                        del history[:-16]
                continue
            if msg_type == "audio":
                session = store.get_voice_session(session_id) or session
                language = session.language
                recording_consent = session.recording_consent
                pcm_b64 = payload.get("pcm_base64") or ""
                pcm = base64.b64decode(pcm_b64) if pcm_b64 else b""
                # Legacy demo override — only when STT is mock.
                override = None
                if payload.get("mock_transcript") and isinstance(stt, MockSttClient):
                    override = str(payload["mock_transcript"])
                result = await run_voice_turn(
                    store,
                    clinic_id=session.clinic_id,
                    voice_session_id=session.id,
                    language=language,
                    pcm=pcm or b"\x00\x00",
                    stt=stt,
                    tts=tts,
                    llm=llm,
                    history=history,
                    recording_consent=recording_consent,
                    user_text_override=override,
                    on_audio_chunk=_chunk_sender(websocket),
                )
                _after_turn(store, settings, session.id, result)
                await _send_turn(websocket, result)
                if result.user_text:
                    history.append({"role": "user", "content": result.user_text})
                    history.append({"role": "assistant", "content": result.assistant_text})
                    if len(history) > 16:
                        del history[:-16]
                continue
            if msg_type == "close":
                store.update_voice_session(
                    session_id, status="closed", closed_at=datetime.now(timezone.utc)
                )
                await websocket.send_json({"type": "closed"})
                break
            await websocket.send_json({"type": "error", "code": "unknown_message"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json(
            {"type": "error", "code": "voice_pipeline_error", "detail": str(exc)}
        )
        await websocket.close(code=1011)


def _after_turn(store, settings, voice_session_id: UUID, result) -> None:
    conversation_service.persist_turn_if_consented(
        store, settings, voice_session_id=voice_session_id, result=result
    )
    for item in result.tool_results or []:
        if item.get("tool") != "escalate" or not item.get("accepted"):
            continue
        handover_id = (item.get("result") or {}).get("handover_id")
        if not handover_id:
            continue
        try:
            conversation_service.link_handover_conversation(
                store,
                settings,
                voice_session_id=voice_session_id,
                handover_id=UUID(str(handover_id)),
            )
        except Exception:
            continue


def _chunk_sender(websocket: WebSocket):
    async def _send(index: int, sentence: str, audio) -> None:
        await websocket.send_json(
            {
                "type": "audio_chunk",
                "index": index,
                "text": sentence,
                "audio_base64": base64.b64encode(audio.pcm_bytes).decode("ascii"),
                "audio_content_type": audio.content_type,
                "audio_sample_rate": audio.sample_rate,
            }
        )

    return _send


async def _send_turn(websocket: WebSocket, result) -> None:
    audio_b64 = None
    content_type = None
    sample_rate = None
    if result.audio is not None:
        audio_b64 = base64.b64encode(result.audio.pcm_bytes).decode("ascii")
        content_type = result.audio.content_type
        sample_rate = result.audio.sample_rate
    await websocket.send_json(
        {
            "type": "turn",
            "user_text": result.user_text,
            "assistant_text": result.assistant_text,
            "tool_results": result.tool_results,
            "escalated": result.escalated,
            "refused_medical": result.refused_medical,
            "llm_failed": result.llm_failed,
            "booking_confirmed": result.booking_confirmed,
            "language": result.language,
            "audio_base64": audio_b64,
            "audio_content_type": content_type,
            "audio_sample_rate": sample_rate,
            "latency_ms": result.latency_ms,
        }
    )
