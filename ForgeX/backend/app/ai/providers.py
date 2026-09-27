"""LLM provider abstraction (Anthropic primary, OpenAI fallback). Plain REST via httpx."""
from __future__ import annotations

import json

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.core.errors import AiProcessingError
from app.core.logging import get_logger

log = get_logger("llm")
settings = get_settings()


class Message(BaseModel):
    role: str
    content: str


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise AiProcessingError("LLM returned no JSON object.")
    return json.loads(text[start : end + 1])


async def _anthropic(messages: list[Message], timeout: int) -> tuple[dict, str, int, int]:
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    conv = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": settings.llm_model_anthropic, "max_tokens": 2048, "system": system, "messages": conv},
        )
    if r.status_code != 200:
        raise AiProcessingError(f"Anthropic API error {r.status_code}: {r.text[:200]}")
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return _extract_json(text), settings.llm_model_anthropic, data.get("usage", {}).get("input_tokens", 0), data.get("usage", {}).get("output_tokens", 0)


async def _openai(messages: list[Message], timeout: int) -> tuple[dict, str, int, int]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "content-type": "application/json"},
            json={
                "model": settings.llm_model_openai,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "response_format": {"type": "json_object"},
            },
        )
    if r.status_code != 200:
        raise AiProcessingError(f"OpenAI API error {r.status_code}: {r.text[:200]}")
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return _extract_json(text), settings.llm_model_openai, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


async def llm_complete(messages: list[Message]) -> tuple[dict, str, int, int]:
    """Returns (json_dict, model_name, prompt_tokens, completion_tokens). One fallback hop."""
    order = []
    if settings.llm_provider in ("auto", "anthropic") and settings.anthropic_api_key:
        order.append(("anthropic", _anthropic))
    if settings.llm_provider in ("auto", "openai") and settings.openai_api_key:
        order.append(("openai", _openai))
    if not order:
        raise AiProcessingError("No LLM provider configured (set ANTHROPIC_API_KEY or OPENAI_API_KEY).")
    last_err: Exception | None = None
    for name, fn in order:
        try:
            return await fn(messages, settings.llm_timeout_sec)
        except Exception as e:  # noqa: BLE001
            log.warning("llm_provider_failed", provider=name, error=str(e)[:150])
            last_err = e
    raise AiProcessingError(f"All LLM providers failed: {last_err}")


def llm_available() -> bool:
    if settings.llm_provider == "off":
        return False
    return bool(settings.anthropic_api_key or settings.openai_api_key)
