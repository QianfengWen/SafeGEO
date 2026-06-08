import pytest

from safegeo.serving import (
    infer_provider,
    resolve_endpoint,
    resolve_mode,
    structured_kwargs,
)


def test_infer_provider_localhost():
    assert infer_provider("http://127.0.0.1:8000/v1") == "vllm"
    assert infer_provider("http://localhost:8000/v1") == "vllm"
    assert infer_provider("http://0.0.0.0:8000/v1") == "vllm"
    assert infer_provider(None) == "vllm"
    assert infer_provider("") == "vllm"


def test_infer_provider_hosted():
    assert infer_provider("https://openrouter.ai/api/v1") == "openrouter"
    assert infer_provider("https://api.openai.com/v1") == "openai"


def test_infer_provider_other_is_custom():
    assert infer_provider("https://example.com/v1") == "custom"
    assert infer_provider("https://my-proxy.internal:9000/v1") == "custom"


def test_resolve_endpoint_vllm_preset(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    url, key = resolve_endpoint("vllm", None, None)
    assert url == "http://127.0.0.1:8000/v1"
    assert key == "EMPTY"


def test_resolve_endpoint_openai_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    url, key = resolve_endpoint("openai", None, None)
    assert url == "https://api.openai.com/v1"
    assert key == "sk-from-env"


def test_resolve_endpoint_explicit_overrides_preset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    url, key = resolve_endpoint("openai", "https://proxy.local/v1", "sk-explicit")
    assert url == "https://proxy.local/v1"
    assert key == "sk-explicit"


def test_resolve_endpoint_openrouter_reads_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-from-env")
    url, key = resolve_endpoint("openrouter", None, None)
    assert url == "https://openrouter.ai/api/v1"
    assert key == "or-from-env"


def test_resolve_mode_auto():
    assert resolve_mode("auto", "vllm") == "guided_json"
    assert resolve_mode("auto", "openai") == "json_object"
    assert resolve_mode("auto", "openrouter") == "json_object"
    assert resolve_mode("auto", "custom") == "json_object"


def test_resolve_mode_explicit_passthrough():
    assert resolve_mode("guided_json", "openai") == "guided_json"
    assert resolve_mode("json_object", "vllm") == "json_object"
    assert resolve_mode("off", "vllm") == "off"


def test_structured_kwargs_guided_json_with_schema():
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    assert structured_kwargs("guided_json", schema) == {"extra_body": {"guided_json": schema}}


def test_structured_kwargs_guided_json_none():
    assert structured_kwargs("guided_json", None) == {}


def test_structured_kwargs_json_object():
    assert structured_kwargs("json_object", None) == {"response_format": {"type": "json_object"}}
    assert structured_kwargs("json_object", {"x": 1}) == {"response_format": {"type": "json_object"}}


def test_structured_kwargs_off():
    assert structured_kwargs("off", None) == {}
    assert structured_kwargs("off", {"x": 1}) == {}


def test_structured_kwargs_unknown_raises():
    with pytest.raises(ValueError):
        structured_kwargs("nonsense", None)
