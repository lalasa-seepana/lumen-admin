"""Gated live smoke for Gnani + Evon. Never runs in default CI.

Enable only when secrets and GPU exist:
  LALA_LIVE_VOICE=1 GNANI_API_KEY=... LLM_BASE_URL=... pytest app/tests/test_gnani_evon_live.py -q -m live
"""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.services.gnani_speech import GnaniSttAdapter, GnaniTtsAdapter
from app.services.llm_evon import EvonOpenAIClient

pytestmark = pytest.mark.live


def _live_enabled() -> bool:
    return os.getenv("LALA_LIVE_VOICE", "").strip() == "1"


@pytest.mark.skipif(not _live_enabled(), reason="Set LALA_LIVE_VOICE=1 with Gnani+LLM secrets")
@pytest.mark.asyncio
async def test_live_gnani_tts_and_evon_chat():
    settings = Settings()
    assert settings.gnani_configured, "GNANI_API_KEY required"
    assert settings.llm_configured, "LLM_BASE_URL required"

    tts = GnaniTtsAdapter(settings)
    audio = await tts.synthesize("Hello from Clinic Dial live smoke.", language="en-IN")
    assert len(audio.pcm_bytes) > 0

    llm = EvonOpenAIClient(settings)
    turn = await llm.complete(
        messages=[{"role": "user", "content": "Say you are an AI receptionist in one short sentence."}],
        language="en-IN",
    )
    assert turn.assistant_text or turn.tool_calls
