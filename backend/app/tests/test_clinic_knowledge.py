from __future__ import annotations

from uuid import uuid4

from app.services.clinic_knowledge import build_clinic_knowledge, clinic_knowledge_prompt_block
from app.services.clinic_store import reset_clinic_store
from app.services.voice_pipeline import split_spoken_sentences, trim_history
from app.services.voice_tools import execute_tool


def test_get_clinic_knowledge_tool_returns_approved_facts():
    store = reset_clinic_store()
    clinic, _ = store.create_clinic_for_owner(
        user_id=uuid4(), name="Knowledge Clinic", timezone_name="Asia/Kolkata"
    )
    store.create_service(
        clinic_id=clinic.id,
        name="Swedish Massage",
        category="Relax",
        duration_minutes=60,
        price_paise=250000,
    )
    store.add_availability_window(
        clinic_id=clinic.id, weekday=0, start_minute=9 * 60, end_minute=17 * 60
    )

    ok, result, reason = execute_tool(
        store,
        clinic_id=clinic.id,
        voice_session_id=None,
        tool_name="get_clinic_knowledge",
        arguments={},
    )
    assert ok is True
    assert reason is None
    assert result["name"] == "Knowledge Clinic"
    assert result["services"][0]["name"] == "Swedish Massage"
    assert result["opening_hours"][0]["day"] == "Mon"
    prompt = clinic_knowledge_prompt_block(store, clinic.id)
    assert "Swedish Massage" in prompt
    assert "do not invent" in prompt.lower() or "Escalate" in prompt or "escalate" in prompt


def test_sentence_split_and_history_trim():
    assert split_spoken_sentences("Hello. How are you?") == ["Hello.", "How are you?"]
    history = [{"role": "user", "content": str(i)} for i in range(20)]
    assert len(trim_history(history)) == 8
    assert build_clinic_knowledge(reset_clinic_store(), uuid4())["found"] is False
