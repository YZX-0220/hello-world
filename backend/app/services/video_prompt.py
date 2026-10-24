"""The preview and the video adapter use exactly the same prompt compiler."""

from app.schemas.agent import VideoBrief


def compile_video_prompt(spec: VideoBrief, suggested_prompt: str | None = None) -> str:
    fields = [
        ("objective", "创作目标"), ("audience", "目标受众"), ("language", "内容语言"),
        ("subject", "画面主体"), ("scene", "场景与分镜"), ("visual_style", "视觉风格"),
        ("camera", "镜头运动"), ("motion", "主体动作"), ("lighting", "光线与氛围"),
        ("narration", "旁白"), ("negative_prompt", "避免出现"),
        ("duration_seconds", "总时长（秒）"), ("aspect_ratio", "画幅"),
    ]
    if not any(getattr(spec, key) for key, _ in fields[:10]) and not suggested_prompt:
        return ""
    lines = []
    if suggested_prompt and suggested_prompt.strip():
        lines.append(f"视频创作描述：\n{suggested_prompt.strip()}")
    lines.extend(
        f"{label}：{value}" for key, label in fields
        if (value := getattr(spec, key)) is not None and str(value).strip()
    )
    if spec.first_frame_asset_id:
        lines.append("素材用途：以提供的首帧为起始画面，保持主体一致，从首帧展开运动。")
    if spec.last_frame_asset_id:
        lines.append("素材用途：以提供的尾帧为结束画面，完成连贯过渡。")
    if spec.reference_asset_ids:
        lines.append("素材用途：提供的图片用于人物、物体或风格参考，不作为首尾帧。")
    return "\n\n".join(lines)
