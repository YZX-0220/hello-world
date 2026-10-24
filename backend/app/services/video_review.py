"""Render the reviewed plan from the exact brief that will be sent to the video provider."""

from app.schemas.agent import AgentOutput, VideoBrief

REVIEW_CLOSING = "如果不再修改，那么可以根据我给出的方案进行生成视频。"
REQUIRED_REVIEW_FIELDS = ("subject", "scene", "camera", "motion", "lighting", "visual_style")


def review_markdown(
    spec: VideoBrief,
    output: AgentOutput,
    resolution: str,
    *,
    target: dict | None = None,
    changes: list | None = None,
    issues: list[str] | None = None,
    material_notices: list[str] | None = None,
) -> str:
    if issues:
        return "\n".join(
            [
                "### 当前方案需要调整",
                *[f"- {issue}" for issue in issues],
                *[f"- 已完成处理：{note}" for note in material_notices or []],
                "",
                "请完成上述操作后重新点击“AI审理方案”。本次不会提交视频生成。",
            ]
        )
    fields = [
        ("subject", "主体"),
        ("scene", "场景与分镜"),
        ("camera", "镜头设计"),
        ("motion", "主体动作"),
        ("lighting", "光线"),
        ("visual_style", "视觉风格"),
        ("narration", "旁白"),
        ("negative_prompt", "避免出现"),
        ("objective", "用途"),
        ("audience", "受众"),
    ]
    ratio = "随素材自适应" if spec.aspect_ratio == "adaptive" else spec.aspect_ratio
    lines = ["### 最终方案"]
    if target:
        lines.append(f"**生成通道**：{target['label']} · {target['remote_model_id']}")
    lines.extend([f"**生成参数**：{spec.duration_seconds} 秒 · {ratio} · {resolution}", ""])
    lines.extend(f"- **{label}**：{getattr(spec, key) or '未填写'}" for key, label in fields)
    if material_notices:
        lines.extend(["", "### 图片处理说明", *[f"- {note}" for note in material_notices]])
    if changes:

        def label(value):
            if value == "adaptive":
                return "随素材自适应"
            if isinstance(value, bool):
                return "开启" if value else "关闭"
            return str(value)

        lines.extend(["", "### 为适配当前模型作出的调整"])
        lines.extend(
            f"- **{c['label']}**：{label(c['before'])} → {label(c['after'])}。{c['reason']}"
            for c in changes
        )
        lines.extend(["", "上方原始设置和小框保留。点击“生成视频”即采用本页展示的方案与调整。"])
    if output.assumptions:
        lines.extend(["", "### 本次采用的假设", *[f"- {note}" for note in output.assumptions]])
    suggestions = output.suggestions or ["需要调整画面、时长或画幅时，编辑小框并重新审理即可。"]
    lines.extend(["", "### 可选建议", *[f"- {note}" for note in suggestions], "", REVIEW_CLOSING])
    return "\n".join(lines)
