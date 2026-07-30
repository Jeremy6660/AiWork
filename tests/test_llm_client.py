from types import SimpleNamespace

import pytest

import src.zhice_yuxun.llm_client as llm_client
from src.zhice_yuxun.llm_client import (
    LLMError,
    call_llm_json,
    call_llm_json_with_fallback,
)


MESSAGES = [{"role": "user", "content": "只输出 JSON"}]


def _response(content: str, model: str = "mock-model"):
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class _FakeOpenAI:
    def __init__(self, create, **kwargs):
        self.init_kwargs = kwargs
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=create),
        )


def _configure_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)


def test_missing_key_fails_before_creating_client(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(LLMError, match="未配置 DEEPSEEK_API_KEY"):
        call_llm_json("deepseek", MESSAGES)


def test_invalid_json_is_retried_then_reported(monkeypatch):
    _configure_deepseek(monkeypatch)
    calls = 0

    def create(**_kwargs):
        nonlocal calls
        calls += 1
        return _response("不是 JSON")

    monkeypatch.setattr(llm_client, "OpenAI", lambda **kwargs: _FakeOpenAI(create, **kwargs))

    with pytest.raises(LLMError, match="已尝试 2 次"):
        call_llm_json("deepseek", MESSAGES, max_attempts=2)
    assert calls == 2


def test_timeout_uses_requested_timeout_and_retries(monkeypatch):
    _configure_deepseek(monkeypatch)
    init_kwargs = {}
    calls = 0

    def create(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("mock timeout")

    def factory(**kwargs):
        init_kwargs.update(kwargs)
        return _FakeOpenAI(create, **kwargs)

    monkeypatch.setattr(llm_client, "OpenAI", factory)

    with pytest.raises(LLMError, match="mock timeout"):
        call_llm_json("deepseek", MESSAGES, timeout=1.25, max_attempts=3)
    assert init_kwargs["timeout"] == 1.25
    assert calls == 3


def test_transient_failure_succeeds_on_retry(monkeypatch):
    _configure_deepseek(monkeypatch)
    calls = 0

    def create(**_kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("temporary")
        return _response('{"通过": true}', model="recovered-model")

    monkeypatch.setattr(llm_client, "OpenAI", lambda **kwargs: _FakeOpenAI(create, **kwargs))

    result = call_llm_json("deepseek", MESSAGES, max_attempts=3)

    assert result == {"通过": True, "_模型": "recovered-model"}
    assert calls == 3


def test_provider_fallback_uses_next_candidate(monkeypatch):
    attempts = []

    def fake_call(provider, messages, *, timeout, max_attempts):
        attempts.append((provider, messages, timeout, max_attempts))
        if provider == "deepseek":
            raise LLMError("primary unavailable")
        return {"通过": True, "_模型": "qwen-mock"}

    monkeypatch.setattr(llm_client, "call_llm_json", fake_call)

    result = call_llm_json_with_fallback(
        MESSAGES,
        providers=["deepseek", "qwen"],
        timeout=2.0,
        max_attempts=1,
    )

    assert [item[0] for item in attempts] == ["deepseek", "qwen"]
    assert result["_供应商"] == "qwen"
    assert result["通过"] is True
