"""Provider and structured-output helpers for the SafeGEO inference runners.

Works with any OpenAI-compatible endpoint. Provider presets set the base URL and
API-key source; structured-output handling adapts to the provider: vLLM supports
schema-guaranteed decoding via `guided_json`, while OpenAI/OpenRouter use JSON
mode (the schema is still specified in the prompt and recovered by the parser).
"""
from __future__ import annotations

import os
from typing import Any

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "vllm":       {"base_url": "http://127.0.0.1:8000/v1", "key_env": None,                 "default_key": "EMPTY"},
    "openai":     {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY",    "default_key": None},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "default_key": None},
}


def infer_provider(base_url: str | None) -> str:
    if not base_url:
        return "vllm"
    b = base_url.lower()
    if "openrouter.ai" in b:
        return "openrouter"
    if "api.openai.com" in b:
        return "openai"
    if "127.0.0.1" in b or "localhost" in b or "0.0.0.0" in b:
        return "vllm"
    return "custom"


def resolve_endpoint(provider: str, base_url: str | None, api_key: str | None) -> tuple[str, str]:
    """Return (base_url, api_key) from a provider preset plus explicit/env overrides."""
    preset = PROVIDER_PRESETS.get(provider, {})
    url = base_url or preset.get("base_url") or "http://127.0.0.1:8000/v1"
    key = api_key
    if not key:
        env = preset.get("key_env")
        if env:
            key = os.environ.get(env)
    if not key:
        key = preset.get("default_key") or os.environ.get("OPENAI_API_KEY") or "EMPTY"
    return url, key


def resolve_mode(json_mode: str, provider: str) -> str:
    """Resolve 'auto' to a concrete structured-output mode for the provider."""
    if json_mode != "auto":
        return json_mode
    return "guided_json" if provider == "vllm" else "json_object"


def structured_kwargs(mode: str, schema: dict[str, Any] | None) -> dict[str, Any]:
    """Return create() kwargs for the resolved structured-output mode."""
    if mode == "guided_json":
        return {"extra_body": {"guided_json": schema}} if schema is not None else {}
    if mode == "json_object":
        return {"response_format": {"type": "json_object"}}
    if mode == "off":
        return {}
    raise ValueError(f"unknown structured-output mode: {mode}")


def default_headers(provider: str) -> dict[str, str] | None:
    """Optional OpenRouter attribution headers (only if the user sets the env vars)."""
    if provider == "openrouter":
        headers = {}
        ref = os.environ.get("OPENROUTER_REFERER")
        title = os.environ.get("OPENROUTER_TITLE")
        if ref:
            headers["HTTP-Referer"] = ref
        if title:
            headers["X-Title"] = title
        return headers or None
    return None
