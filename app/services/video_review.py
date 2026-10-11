"""Render the reviewed plan from the exact brief that will be sent to the video provider."""

from app.schemas.agent import AgentOutput, VideoBrief

REVIEW_CLOSING = "如果不再修改，那么可以根据我给出的方案进行生成视频。"
REQUIRED_REVIEW_FIELDS = ("subject", "scene", "camera", "motion", "lighting", "visual_style")


def review_markdown(spec: VideoBrief, output: AgentOutput, resolution: str) -> str:
    fields = [
        ("subject", "主体"), ("scene", "场景与分镜"), ("camera", "镜头设计"),
        ("motion", "主体动作"), ("lighting", "光线"), ("visual_style", "视觉风格"),
        ("narration", "旁白"), ("negative_prompt", "避免出现"),
        ("objective", "用途"), ("audience", "受众"),
    ]
    lines = ["### 最终方案", f"**生成参数**：{spec.duration_seconds} 秒 · {spec.aspect_ratio} · {resolution}", ""]
    lines.extend(f"- **{label}**：{getattr(spec, key) or '未填写'}" for key, label in fields)
    if output.assumptions:
        lines.extend(["", "### 本次采用的假设", *[f"- {note}" for note in output.assumptions]])
    suggestions = output.suggestions or ["需要调整画面、时长或画幅时，编辑小框并重新审理即可。"]
    lines.extend(["", "### 可选建议", *[f"- {note}" for note in suggestions], "", REVIEW_CLOSING])
    return "\n".join(lines)
