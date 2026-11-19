"""Render the reviewed plan from the exact brief that will be sent to the video provider."""

from app.schemas.agent import AgentOutput, VideoBrief

REVIEW_CLOSING = "如果不再修改，那么可以根据我给出的方案进行生成视频。"
REQUIRED_REVIEW_FIELDS = ("subject", "scene", "camera", "motion", "lighting", "visual_style")
PORTRAIT_REFERENCE_NOTICE = (
    "参考素材中含有人像元素。请确认图片由与所选视频通道同一方舟账号下的配套图片模型生成；"
    "使用订阅 API 时，也需使用该账号内配套的订阅通道。来源不匹配可能导致审核失败。"
    "使用自备视频 API 时，请搭配自己的图片 API 生成人像素材。"
)


def _duration_text(values: list[int]) -> str:
    ordered = sorted({int(value) for value in values})
    if not ordered:
        return "该模型未声明时长限制"
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{ordered[0]}–{ordered[-1]} 秒（连续可选）"
    return "、".join(str(value) for value in ordered) + " 秒"


def _duration_section(duration_check: dict | None) -> list[str]:
    if not duration_check:
        return []
    supported = [int(value) for value in duration_check.get("supported") or []]
    selected = duration_check.get("selected")
    model = duration_check.get("model") or ""
    lines = ["### 时长校验"]
    if model:
        lines.append(f"- **当前模型**：{model}")
    lines.append(f"- **模型支持时长**：{_duration_text(supported)}")
    if isinstance(selected, int) and selected > 0:
        supported_now = selected in supported if supported else True
        lines.append(f"- **本次选择**：{selected} 秒，{'支持' if supported_now else '不支持'}")
        if not supported_now:
            lines.append("- 请把时长调整为上述可选值后重新审理。")
    return lines


def review_markdown(
    spec: VideoBrief,
    output: AgentOutput,
    resolution: str,
    *,
    target: dict | None = None,
    changes: list | None = None,
    issues: list[str] | None = None,
    material_notices: list[str] | None = None,
    duration_check: dict | None = None,
) -> str:
    duration_lines = _duration_section(duration_check)
    if issues:
        blocks = [
            "### 当前方案需要调整",
            *[f"- {issue}" for issue in issues],
            *[f"- 已完成处理：{note}" for note in material_notices or []],
        ]
        if duration_lines:
            blocks.extend(["", *duration_lines])
        blocks.extend(["", "请完成上述操作后重新点击“AI审理方案”。本次不会提交视频生成。"])
        content = "\n".join(blocks)
        return f"{content}\n\n{PORTRAIT_REFERENCE_NOTICE}" if output.contains_portrait else content
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
    if duration_lines:
        lines.extend([*duration_lines, ""])
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
    if output.contains_portrait:
        lines.extend(["", PORTRAIT_REFERENCE_NOTICE])
    return "\n".join(lines)
