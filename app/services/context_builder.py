"""上下文构建器。

把当前视频方案摘要、历史消息与最新用户消息按固定顺序组织成模型可用的消息列表。
首期使用保守的 Token 估算（只取最近若干条历史），模型真实用量由 Provider 返回后记录。
"""

from app.schemas.agent import VideoBrief

DEFAULT_SYSTEM_PROMPT = """你是「Hello World」AI 视频平台里的创作策划助手（Creative Agent）。
你不只是一个聊天助手。你是视频生成流水线中承上启下的一环：把用户的创作意图，经过专业对话，
整理成一份能交给视频生成模型直接执行的结构化方案与提示词，你的产出最终会被拿去生成视频。

【你应该怎样思考】以导演 / 摄影 / 剪辑视角工作：
- 把用户的模糊想法（"好美""有感觉"）翻译成可执行的视听语言，而不是复述。
- 画面要素写清楚：主体及其动作、环境与道具、镜头（景别/机位/一次只写一个主要运镜，用
  slow/smooth/gentle 这类节奏词描述）、光线（写方向/强弱/色温，例如"暖色侧光""月色清冷"）、
  色彩与氛围、运动节奏。
- 动作按时间顺序讲，一次一个主要运动；把"主体运动"和"镜头运动"分开写，避免歧义。
  （反例："环绕舞者拍摄"；正例："舞者缓慢转身，镜头保持固定构图"）
- 用具体描述表达质感，不要堆空洞的高调词（"电影感/4K/杰作"作用有限）；需要真实感时用
  "超写实、真人实景、杜绝游戏 CG 感、避免镜头漂移"这类直接限制词。
- 主动给专业建议与取舍：时长多长更合适、画幅怎么选、是否配音、镜头如何配合情绪推进。
- 若关键信息不足（主体是谁、给谁看、时长/画幅未定），先在 reply 里引导用户补充；
  除非用户已给出明确方向，否则不要替用户做决定性假设。

【素材语义】用户可能上传素材，务必区分它们，不要混用：
- first_frame_asset_id（首帧）＝视频第一帧，是起幅锚点。描述时从"首帧开始"的运动与镜头展开，
  不要重写一张并不存在的新画面。
- last_frame_asset_id（尾帧）＝最后一帧，是收幅锚点。模型会在首帧与尾帧之间补全过渡。
- reference_asset_ids（参考图）＝锁定人物/物体/风格参考，并不成为视频本身；文字只描述
  运动、运镜与氛围走向。
- source_video_asset_id（源视频）＝视频编辑/重绘/延长的底片；描述聚焦变化与镜头，而非复述原内容。
- audio_asset_id（音频）＝人声或音乐素材，用于音频驱动的人声、节奏或表演呈现。
- 图生视频原则：文字不要重复图片里已有的内容，聚焦"怎么动、往哪动、光线与氛围如何变化"。

【输出契约】只输出一个 JSON 对象：
{
  "reply": <给用户看的自然语言：你做了什么、还缺什么、下一步建议>,
  "state_patch": <本次要修改的方案字段，只放本次要改的，未改字段不要出现>,
  "missing_fields": <仍缺少、需要用户明确的字段名数组，如 ["duration_seconds","aspect_ratio"]>,
  "ready_for_generation": <方案是否已可交给视频生成模型，true/false>,
  "suggested_prompt": <适合视频生成模型的完整提示词：画面 + 一个主运镜 + 光线氛围 + 节奏/时长；
                        可注明从首帧开始的运动；若方案未就绪可为 null>
}
"state_patch" 只能从这些字段里选（务必用这些字段名，不要自创）：
objective / audience / language / duration_seconds / aspect_ratio / mode / visual_style /
subject / scene / camera / motion / lighting / narration / negative_prompt。
其中 mode 取值只能是：text_to_video / first_frame_to_video / first_last_frame_to_video /
reference_image_to_video / video_to_video / video_extend / audio_or_performance_to_video。
duration_seconds 为整数字秒；aspect_ratio 形如 16:9 / 9:16 / 1:1。
negative_prompt 用于描述应避免的画面问题（如现代建筑、车辆、人物、过曝、模糊、卡通风格）。

【联网搜索】若你需要核实实时信息、事实或不确定的资料，且系统已开启联网，可在同一 JSON 里加
"search_requests": ["查询词", ...]（最多 3 个，每个不超过 200 字）。后端会为你搜索并在回复中附上来源。
若系统未开启联网，请忽略，不要输出该字段。"""

# 每轮只取最近若干条消息进上下文（保守预算）
_MAX_HISTORY_MESSAGES = 12

# ---- 长对话摘要 ----
SUMMARY_PREFIX = "对话摘要："
# 摘要正文上限（字符），防止模型一次抛出超长文本
MAX_SUMMARY_LENGTH = 2000
SUMMARY_SYSTEM_PROMPT = """你是「Hello World」AI 视频平台的长对话摘要助手。
请把给定的多轮对话压缩成一段简洁的中文要点摘要，供后续轮次继续对话时作为历史背景使用。

要求：
- 先概括对话主题与用户的创作目标；
- 列出已经确定的关键方案字段（主体/场景/镜头/光线/画幅/时长/视觉风格/负面提示等），已占用的首尾帧、参考图等素材；
- 保留用户的偏好与已下达的约束条件；
- 标注仍缺少、需要用户进一步明确的信息；
- 不要复述整段对话，摘要正文控制在 500 字以内，只输出摘要正文，不要任何前缀/标题/Markdown。"""


def brief_to_text(brief: VideoBrief) -> str:
    """把当前结构化方案 + 素材占用转成一段人可读摘要，便于模型了解现状。"""
    parts: list[str] = []
    mapping = {
        "objective": "目标", "audience": "受众", "language": "语言", "duration_seconds": "时长(秒)",
        "aspect_ratio": "画幅", "mode": "模式", "visual_style": "视觉风格", "subject": "主体",
        "scene": "场景", "camera": "镜头", "motion": "运动", "lighting": "光线", "narration": "旁白",
        "negative_prompt": "负面提示",
    }
    for field, label in mapping.items():
        value = getattr(brief, field, None)
        if value is not None:
            parts.append(f"{label}: {value}")

    # 素材占用情况（重要：让模型知道已有/要用首尾帧或参考图）
    if brief.first_frame_asset_id:
        parts.append("已有首帧素材")
    if brief.last_frame_asset_id:
        parts.append("已有尾帧素材")
    if brief.reference_asset_ids:
        parts.append(f"已有{len(brief.reference_asset_ids)}张参考图")
    if brief.source_video_asset_id:
        parts.append("已有源视频")
    if brief.audio_asset_id:
        parts.append("已有音频素材")

    return "；".join(parts) if parts else "（目前方案为空）"


def build_summary_prompt(messages: list[dict[str, str]], prev_summary: str = "") -> list[dict[str, str]]:
    """构造交给文本模型做摘要的消息列表。

    messages 为待压缩的 [{"role","content"}]（按时间顺序）；prev_summary 为既有历史摘要，
    若有则作为前缀注入，让模型在旧摘要基础上继续扩展，避免信息丢失。
    """
    lines: list[str] = []
    if prev_summary:
        lines.append(f"已有摘要：{prev_summary}")
    lines.append("请对以下这一小段多轮对话做中文要点摘要：")
    for m in messages:
        role = m.get("role", "user")
        label = "用户" if role == "user" else ("助手" if role == "assistant" else str(role))
        lines.append(f"{label}：{m.get('content', '')}")
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _message_index(history: list[dict[str, str]], message_id: str) -> int | None:
    """在按时间顺序的 history 中定位某条消息 id 的下标；找不到返回 None。"""
    for i, item in enumerate(history):
        if item.get("id") == message_id:
            return i
    return None


def build_context(
    brief: VideoBrief,
    history: list[dict[str, str]],
    user_content: str,
    *,
    summary_text: str = "",
    summary_through_message_id: str | None = None,
) -> list[dict[str, str]]:
    """构造发送给模型的消息列表。

    history 为 [{"id","role","content"}]（id 可选），按时间顺序。
    - 当存在摘要（summary_text 非空且 summary_through_message_id 有值）时，把该 id **及之前**的
      历史替换成一条 role=system 的摘要消息，该 id 之后的消息照常加入，避免重复/缺失；
    - 否则回退到只取最近 N 条的历史（首期保守预算）。
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": f"{DEFAULT_SYSTEM_PROMPT}\n\n【当前状态】当前方案：{brief_to_text(brief)}"}
    ]

    summary = (summary_text or "").strip()
    if summary and summary_through_message_id:
        boundary_idx = _message_index(history, summary_through_message_id)
        if boundary_idx is not None:
            messages.append({"role": "system", "content": f"{SUMMARY_PREFIX}{summary}"})
            messages.extend(history[boundary_idx + 1 :])
            messages.append({"role": "user", "content": user_content})
            return messages

    # 未压缩回退：只取最近 N 条
    for item in history[-_MAX_HISTORY_MESSAGES:]:
        messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
    messages.append({"role": "user", "content": user_content})
    return messages
