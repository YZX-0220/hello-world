"""开发/测试用的 Fake 文本 Provider。

不真正调用模型，返回可配置的占位回复，便于在没有真实文本 API 时走通对话链路。
可在测试中通过继承覆写 generate 以模拟特定行为（如返回结构化 JSON、超时、非法 JSON）。
"""

from app.providers.text.base import TextCapabilities, TextProvider, TextResult


class FakeTextProvider(TextProvider):
    code = "fake"

    @property
    def capabilities(self) -> TextCapabilities:
        return TextCapabilities(supports_structured_output=True, supports_tool_call=False, supports_native_search=False)

    async def generate(self, messages: list[dict[str, str]], *, structured: bool = False) -> TextResult:
        # 取最后一条用户消息做简单回显，便于看出对话链路在走
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        reply = f"【Fake 模型】已收到你的描述：{last_user}。我据此为你更新视频方案。"
        structured_payload: dict | None = None
        if structured:
            # 演示结构输出：把用户消息作为主体写入方案
            structured_payload = {"subject": last_user or None}
        return TextResult(reply=reply, structured=structured_payload, model="fake-model", finish_reason="stop")


# 模块级唯一实例，便于测试/开发统一引用
fake_text_instance = FakeTextProvider()
