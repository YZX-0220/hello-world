"""OpenAI 兼容文本 Provider。

对接绝大多数兼容 OpenAI /chat/completions 的模型服务（DeepSeek、智谱 GLM、Kimi、
通义 Qwen、MiniMax 等）。接入真实文本 API 的入口：在 .env 填 TEXT_BASE_URL/TEXT_API_KEY/TEXT_MODEL
并把 TEXT_PROVIDER 设为 openai_compatible 即可。
"""

import json

import httpx

from app.core.config import settings
from app.providers.text.base import TextCapabilities, TextProvider, TextProviderError, TextResult


def _parse_structured(content: str) -> dict:
    """把模型返回的内容解析为结构化 JSON，容错 markdown 代码围栏。失败抛 AGENT_OUTPUT_INVALID。"""
    text = content.strip()
    if text.startswith("```"):
        # ```json\n {...} \n``` 形式
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
        # 声明支持结构输出与工具调用（具体取决于所选模型，是否真正启用由调用方判断）
        return TextCapabilities(supports_structured_output=True, supports_tool_call=True, supports_native_search=False)

    async def generate(self, messages: list[dict[str, str]], *, structured: bool = False) -> TextResult:
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
            retryable = resp.status_code >= 500
            raise TextProviderError(
                "TEXT_PROVIDER_UNAVAILABLE", f"文本模型返回 {resp.status_code}", retryable=retryable
            )

        data = resp.json()
        choices = data.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""

        structured_data = None
        if structured and content:
            structured_data = _parse_structured(content)

        usage = data.get("usage") or {}
        return TextResult(
            reply=content,
            structured=structured_data,
            model=data.get("model", ""),
            request_id=resp.headers.get("x-request-id"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
        )
