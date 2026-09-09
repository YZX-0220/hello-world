"""OpenAI 兼容文本 Provider。

对接绝大多数兼容 OpenAI /chat/completions 的模型服务（DeepSeek、智谱 GLM、Kimi、
通义 Qwen、MiniMax 等）。接入真实文本 API 的入口：在 .env 填 TEXT_BASE_URL/TEXT_API_KEY/TEXT_MODEL
并把 TEXT_PROVIDER 设为 openai_compatible 即可。

结构化输出：请求 response_format=json_object；若模型偶发返回非合法 JSON，会做一次
「受控修复」——追加提示让模型重新输出纯 JSON（《实施计划》4.4：非法 JSON 有一次受控修复）。
"""

import json

import httpx

from app.core.config import settings
from app.providers.text.base import TextCapabilities, TextProvider, TextProviderError, TextResult


def _parse_structured(content: str) -> dict:
    """把模型返回的内容解析为结构化 JSON，容错 markdown 代码围栏。失败抛 AGENT_OUTPUT_INVALID。"""
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[len(parts) - 2] if parts[-1].strip() == "" else parts[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
            text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TextProviderError("AGENT_OUTPUT_INVALID", "AI 结构化输出无法校验", retryable=False) from exc


class OpenAICompatibleTextProvider(TextProvider):
    code = "openai_compatible"

    @property
    def capabilities(self) -> TextCapabilities:
        return TextCapabilities(supports_structured_output=True, supports_tool_call=True, supports_native_search=False)

    async def _post(self, messages: list[dict[str, str]], structured: bool) -> tuple[str, dict]:
        base_url = settings.text_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        payload: dict = {
            "model": settings.text_model,
            "messages": messages,
            "temperature": 0.7,
        }
        if structured:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {settings.text_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.text_timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise TextProviderError("TEXT_PROVIDER_TIMEOUT", "文本模型响应超时", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise TextProviderError("TEXT_PROVIDER_UNAVAILABLE", "文本模型暂时不可用", retryable=True) from exc
        if resp.status_code == 429:
            raise TextProviderError("TEXT_PROVIDER_UNAVAILABLE", "文本模型限流", retryable=True)
        if resp.status_code >= 400:
            raise TextProviderError(
                "TEXT_PROVIDER_UNAVAILABLE", f"文本模型返回 {resp.status_code}", retryable=resp.status_code >= 500
            )
        data = resp.json()
        choices = data.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        return content, data

    async def generate(self, messages: list[dict[str, str]], *, structured: bool = False) -> TextResult:
        content, data = await self._post(messages, structured)

        structured_data = None
        if structured and content:
            try:
                structured_data = _parse_structured(content)
            except TextProviderError:
                # 受控修复一次：追加提示，让模型重新输出纯 JSON
                fixed_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "你上次的输出不是合法的 JSON。请重新只输出一个 JSON 对象，不要任何多余文字，也不要 markdown 代码块。",
                    },
                ]
                content, data = await self._post(fixed_messages, structured)
                if content:
                    structured_data = _parse_structured(content)

        choices = (data or {}).get("choices") or [{}]
        choice = choices[0]
        usage = (data or {}).get("usage") or {}
        return TextResult(
            reply=content,
            structured=structured_data,
            model=(data or {}).get("model", ""),
            request_id=None,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
        )
