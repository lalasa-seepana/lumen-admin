from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import httpx

from app.core.config import Settings
from app.services.voice_tools import SYSTEM_PROMPT, tool_specs


@dataclass
class LlmTurn:
    assistant_text: str
    tool_calls: List[Dict[str, Any]]
    raw: Dict[str, Any]


class LlmClient(Protocol):
    async def complete(
        self,
        *,
        messages: List[Dict[str, Any]],
        language: str,
        clinic_context: Optional[str] = None,
    ) -> LlmTurn: ...


class EvonOpenAIClient:
    """OpenAI-compatible chat client.

    Works with:
    - OpenAI (`LLM_BASE_URL=https://api.openai.com`, `LLM_API_KEY=sk-...`)
    - Self-hosted Evon via vLLM/SGLang (same /v1/chat/completions shape)
    """

    def __init__(self, settings: Settings, http: Optional[httpx.AsyncClient] = None):
        self.settings = settings
        self._http = http

    async def complete(
        self,
        *,
        messages: List[Dict[str, Any]],
        language: str,
        clinic_context: Optional[str] = None,
    ) -> LlmTurn:
        if not self.settings.llm_configured:
            raise RuntimeError("llm_not_configured")

        base = self.settings.llm_base_url.rstrip("/")
        # Accept either https://api.openai.com or https://api.openai.com/v1
        if base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = self.settings.resolved_llm_api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self.settings.llm_provider == "openrouter":
            # OpenRouter ranking / attribution headers (optional but recommended).
            headers["HTTP-Referer"] = "http://127.0.0.1:3002"
            headers["X-Title"] = "Clinic Dial — Rhea"

        system = SYSTEM_PROMPT + f"\nCaller language BCP-47: {language}."
        if clinic_context:
            system += (
                "\n\nApproved clinic facts (authoritative; do not invent beyond this):\n"
                f"{clinic_context}"
            )
        payload = {
            "model": self.settings.llm_model,
            "messages": [{"role": "system", "content": system}, *messages],
            "tools": tool_specs(),
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 350,
        }

        client = self._http or httpx.AsyncClient(timeout=60.0)
        owns = self._http is None
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                detail = (response.text or "")[:300]
                raise RuntimeError(f"llm_http_{response.status_code}:{detail}")
            data = response.json()
        finally:
            if owns:
                await client.aclose()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        return LlmTurn(
            assistant_text=str(message.get("content") or "").strip(),
            tool_calls=tool_calls,
            raw=data,
        )


class MockLlmClient:
    """Deterministic brain when Evon/GPU is unavailable — never hits a network.

    Used for unit tests and for speech-only demos (Gnani STT/TTS + this mock).
    """

    def __init__(self, script: Optional[List[LlmTurn]] = None):
        self.script = list(script or [])
        self.calls: List[List[Dict[str, Any]]] = []

    async def complete(
        self,
        *,
        messages: List[Dict[str, Any]],
        language: str,
        clinic_context: Optional[str] = None,
    ) -> LlmTurn:
        self.calls.append(messages)
        _ = clinic_context
        if self.script:
            return self.script.pop(0)

        user_text = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_text = str(message.get("content") or "").strip()
                break
        lowered = user_text.lower()

        # After tool results, close with a spoken answer (no more tools).
        if messages and messages[-1].get("role") == "tool":
            last_tool = str(messages[-1].get("content") or "")
            if "services" in last_tool or "opening_hours" in last_tool:
                return LlmTurn(
                    assistant_text=(
                        "I'm Rhea, an AI receptionist. I have the approved clinic details. "
                        "Would you like to book a service?"
                    ),
                    tool_calls=[],
                    raw={"mock": True, "language": language, "after_tools": True},
                )
            return LlmTurn(
                assistant_text=(
                    "I'm Rhea, an AI receptionist. Based on what I checked, "
                    "I can help with services and booking. What would you like to do next?"
                ),
                tool_calls=[],
                raw={"mock": True, "language": language, "after_tools": True},
            )

        wants_knowledge = any(
            word in lowered
            for word in (
                "hour",
                "open",
                "close",
                "price",
                "cost",
                "where",
                "address",
                "website",
                "knowledge",
                "about the clinic",
            )
        )
        wants_services = any(
            word in lowered
            for word in ("service", "services", "offer", "treatment", "what do you")
        )
        if wants_knowledge:
            return LlmTurn(
                assistant_text="I'm Rhea, an AI receptionist. Let me check the approved clinic facts.",
                tool_calls=[
                    {
                        "id": "call_knowledge",
                        "type": "function",
                        "function": {"name": "get_clinic_knowledge", "arguments": "{}"},
                    }
                ],
                raw={"mock": True, "language": language},
            )
        if wants_services or not user_text:
            return LlmTurn(
                assistant_text=(
                    "I'm Rhea, an AI receptionist. Let me check which services are available."
                ),
                tool_calls=[
                    {
                        "id": "call_list",
                        "type": "function",
                        "function": {"name": "list_services", "arguments": "{}"},
                    }
                ],
                raw={"mock": True, "language": language},
            )

        return LlmTurn(
            assistant_text=(
                "I'm Rhea, an AI receptionist. I can list clinic services, check availability, "
                "or help book an appointment. What would you like to do?"
            ),
            tool_calls=[],
            raw={"mock": True, "language": language, "spoken_only": True},
        )
