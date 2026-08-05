"""OpenAI 兼容的大模型 JSON 调用层。

默认只启用 DeepSeek；通义与 GLM 适配器在对应 Key 存在时自动可用。所有
调用都必须返回 JSON，并由调用方继续做业务字段校验。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class LLMError(RuntimeError):
    """供应商不可用、调用失败或返回内容无法解析。"""


@dataclass(frozen=True)
class ProviderConfig:
    key_env: str
    base_url_env: str
    model_env: str
    default_base_url: str
    default_model: str


PROVIDERS = {
    "deepseek": ProviderConfig(
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "https://api.deepseek.com",
        "deepseek-v4-flash",
    ),
    "qwen": ProviderConfig(
        "QWEN_API_KEY",
        "QWEN_BASE_URL",
        "QWEN_MODEL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-plus",
    ),
    "glm": ProviderConfig(
        "GLM_API_KEY",
        "GLM_BASE_URL",
        "GLM_MODEL",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4-flash",
    ),
}


def available_providers() -> list[str]:
    return [
        name
        for name, config in PROVIDERS.items()
        if os.getenv(config.key_env, "").strip()
    ]


def _text_from_content(content: Any) -> str:
    """提取消息中的文本，不破坏可能存在的多模态 content。"""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


def _ensure_json_instruction(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回带 JSON 指令的消息副本，兼容 DeepSeek 的 json_object 前置条件。"""

    prepared = [dict(message) for message in messages]
    joined = "\n".join(_text_from_content(message.get("content")) for message in prepared)
    if "json" in joined.casefold():
        return prepared

    instruction = "请以 JSON 格式输出。"
    if prepared and prepared[-1].get("role") == "user":
        content = prepared[-1].get("content")
        if isinstance(content, str):
            prepared[-1]["content"] = f"{content}\n{instruction}"
            return prepared
    prepared.append({"role": "user", "content": instruction})
    return prepared


def call_llm_json(
    provider: str,
    messages: list[dict[str, Any]],
    *,
    timeout: float = 60.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if max_attempts < 1:
        raise ValueError("max_attempts 必须至少为 1")
    if provider not in PROVIDERS:
        raise LLMError(f"不支持的模型供应商：{provider}")
    config = PROVIDERS[provider]
    api_key = os.getenv(config.key_env, "").strip()
    if not api_key:
        raise LLMError(f"未配置 {config.key_env}")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv(config.base_url_env, config.default_base_url),
        timeout=timeout,
        max_retries=0,
    )
    model = os.getenv(config.model_env, config.default_model)
    # DeepSeek 的 json_object 模式要求 prompt 中必须出现 "json" 字样，否则返回 400。
    # 在重试循环外只准备一次，保证每次尝试使用相同请求内容且不修改调用方数据。
    request_messages = _ensure_json_instruction(messages)
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=request_messages,  # type: ignore[arg-type]
                temperature=0,
                response_format={"type": "json_object"},
                stream=False,
            )
            raw = response.choices[0].message.content or ""
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise LLMError("模型 JSON 顶层必须是对象")
            data["_模型"] = response.model or model
            return data
        except Exception as exc:  # SDK 的网络/HTTP/解析异常统一转换
            last_error = exc
            if attempt + 1 < max_attempts:
                time.sleep(0.4 * (2**attempt))
    raise LLMError(f"{provider} 调用失败（已尝试 {max_attempts} 次）：{last_error}")


def call_llm_json_with_fallback(
    messages: list[dict[str, Any]],
    *,
    providers: list[str] | None = None,
    timeout: float = 60.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """按给定顺序尝试可用供应商，全部失败时返回统一错误。

    该函数不隐式开启任何供应商：未配置 Key 的供应商不会进入默认候选列表；
    调用方也可以显式传入候选顺序，便于审核等场景实施可审计降级。
    """

    candidates = available_providers() if providers is None else providers
    if not candidates:
        raise LLMError("没有配置可用的大模型供应商")

    errors: list[str] = []
    for provider in candidates:
        try:
            result = call_llm_json(
                provider,
                messages,
                timeout=timeout,
                max_attempts=max_attempts,
            )
            result["_供应商"] = provider
            return result
        except LLMError as exc:
            errors.append(f"{provider}: {exc}")
    raise LLMError("所有候选供应商均调用失败：" + "；".join(errors))
