"""开发/测试用的 Fake 文本 Provider。

不真正调用模型，返回可配置的占位回复，便于在没有真实文本 API 时走通对话链路。
可在测试中通过继承覆写 generate 以模拟特定行为（如返回结构化 JSON、超时、非法 JSON）。
"""

from typing import Any

from app.providers.text.base import TextCapabilities, TextProvider, TextResult


class FakeTextProvider(TextProvider):
    code = "fake"

    @property
    def capabilities(self) -> TextCapabilities:
        return TextCapabilities(
            supports_structured_output=True, supports_tool_call=False, supports_native_search=False
        )

    async def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        structured: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ) -> TextResult:
        # 取最后一条用户消息做简单回显，便于看出对话链路在走
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        sys_text = "\n".join(
            str(m.get("content", "")) for m in messages if m.get("role") == "system"
        )

        if "国际传播微电影与AI视频总编剧" in sys_text:
            outline_reply = (
                "【核心立意】以真实细腻的视听细节为媒，传递温暖人文与当代美学价值。\n"
                "【故事脉络】\n"
                "1. 开篇建立自然环境与核心人物关系，铺垫视觉基调。\n"
                "2. 中段通过具体物理动作与光影流转推进叙事高潮。\n"
                "3. 尾声以温暖微笑与光晕转场收束情感共鸣。"
            )
            return TextResult(
                reply=outline_reply, structured=None, model="fake-model", finish_reason="stop"
            )

        if "AI 视觉执行导演" in sys_text and structured:
            import re

            match = re.search(r"拆解为\s*(\d+)\s*个片段", sys_text)
            seg_count = int(match.group(1)) if match else 3
            cn_nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
            segments = []
            for idx in range(1, seg_count + 1):
                cn = cn_nums[idx] if idx <= 10 else str(idx)
                segments.append(
                    {
                        "index": idx,
                        "title": f"片段{cn}",
                        "duration": 15,
                        "timeline_prompt": (
                            f"0-5秒：全景镜头缓慢推进，展示片段{cn}的主体环境与柔和自然光；\n"
                            f"5-10秒：切中景跟拍，主体完成核心物理动作与环境互动；\n"
                            f"10-15秒：推至特写镜头，光线柔和变化完成叙事收尾。"
                        ),
                    }
                )
            director_payload: dict[str, Any] = {
                "style_node_content": "【整体视觉风格】4K纪录片质感，暖调自然光，浅景深，平稳电影运镜。",
                "cultural_node_content": "【目标地区】按所选国家文化语境适配。\n【负面提示词】低画质、闪烁、肢体畸变。",
                "image_asset_prompts": "【核心图片素材 1】写实电影级首帧构图，自然光影，主体服装与神态清晰。",
                "segments": segments,
            }
            return TextResult(
                reply="{}", structured=director_payload, model="fake-model", finish_reason="stop"
            )

        reply = f"【Fake 模型】已收到你的描述：{last_user}。我据此为你更新视频方案。"
        structured_payload: dict | None = None
        if structured:
            # 演示结构输出：把用户消息作为主体写入方案
            structured_payload = {"subject": last_user or None}
            if any("本轮是一次性 AI 审理" in m.get("content", "") for m in messages):
                structured_payload = {
                    "state_patch": {
                        "subject": "示例主体",
                        "scene": "简洁的演示场景",
                        "camera": "固定机位",
                        "motion": "主体缓慢移动",
                        "lighting": "柔和自然光",
                        "visual_style": "写实",
                    },
                    "assumptions": ["当前使用开发测试模型，创作内容仅为示例。"],
                }
        return TextResult(
            reply=reply, structured=structured_payload, model="fake-model", finish_reason="stop"
        )


# 模块级唯一实例，便于测试/开发统一引用
fake_text_instance = FakeTextProvider()
