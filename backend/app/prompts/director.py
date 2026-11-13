"""Stage 1 & Stage 2 导演 Agent Prompt 构造与时长/序号工具。"""

_CN_DIGITS = ("零", "一", "二", "三", "四", "五", "六", "七", "八", "九")


def to_cn_index(num: int) -> str:
    """将正整数（1~99）转为中文序号（如 1->一, 11->十一, 20->二十）。"""
    if num <= 0:
        return str(num)
    if num < 10:
        return _CN_DIGITS[num]
    if num == 10:
        return "十"
    if num < 20:
        return f"十{_CN_DIGITS[num % 10]}"
    if num < 100:
        tens, ones = divmod(num, 10)
        return f"{_CN_DIGITS[tens]}十" if ones == 0 else f"{_CN_DIGITS[tens]}十{_CN_DIGITS[ones]}"
    return str(num)


def _snap_duration(seconds: int) -> int:
    """将单片段时长向上对齐到视频模型常用档位（5 / 10 / 15 秒）。"""
    if seconds <= 5:
        return 5
    if seconds <= 10:
        return 10
    return 15


def allocate_segment_durations(total_duration: int, segment_count: int) -> list[int]:
    """分配各片段时长（1~15 秒），优先前 N-1 段为 15 秒，末段承载尾差并对齐 5/10/15 档位。

    若总时长不足以让前 N-1 段都取 15 秒（例如 20 秒拆 2 段），则先按 5 秒档位均分封顶 15 秒。
    """
    if segment_count <= 1:
        return [_snap_duration(min(15, max(5, total_duration)))]

    if total_duration > (segment_count - 1) * 15:
        head = [15] * (segment_count - 1)
        tail = _snap_duration(min(15, max(5, total_duration - (segment_count - 1) * 15)))
        return [*head, tail]

    base = max(5, (total_duration // segment_count // 5) * 5)
    base = min(15, base)
    durations = [base] * segment_count
    remainder = total_duration - base * segment_count
    idx = 0
    while remainder >= 5 and idx < segment_count:
        add = min(15 - durations[idx], 5)
        if add > 0:
            durations[idx] += add
            remainder -= add
        idx += 1
    if remainder > 0:
        for i in range(segment_count - 1, -1, -1):
            if durations[i] < 15:
                durations[i] = _snap_duration(min(15, durations[i] + remainder))
                break
    return durations


def _timeline_slots_hint(duration: int) -> str:
    if duration <= 5:
        return "0-5秒"
    if duration <= 10:
        return "0-5秒 / 5-10秒"
    return "0-5秒 / 5-10秒 / 10-15秒"


def build_outline_messages(
    *,
    total_duration: int,
    recommended_segments: int,
    user_idea: str,
    current_draft: str | None = None,
    revision_instruction: str | None = None,
) -> list[dict[str, str]]:
    """构造 Stage 1（总编剧 Agent）的对话消息列表，避免 str.format 因用户输入花括号报错。"""
    system_prompt = (
        "你是一位资深的“国际传播微电影与AI视频总编剧”。\n"
        f"用户的目标是制作一部总时长为 {total_duration} 秒的视频"
        f"（预计将切分为 {recommended_segments} 个 15 秒左右的连续片段）。\n\n"
        "【你的核心任务】\n"
        "1. 若为首次生成：根据用户的核心思想，提炼【核心立意】，并按起承转合展开【故事脉络】。"
        f"叙事体量必须严格匹配 {total_duration} 秒所能容纳的镜头信息量，避免空洞说教，用具体的视听画面讲故事。\n"
        "2. 若为迭代修改：用户会提供【当前剧本草稿】（可能包含用户的手动修改）以及【修改方向指令】。"
        "你必须尊重并保留用户在草稿中已确认的细节，仅针对修改指令进行调整润色。\n\n"
        "【输出格式要求】\n"
        "直接输出剧本正文（包含【核心立意】与【故事脉络】两部分），"
        "不要输出任何寒暄或多余的解释性前言，以便前端直接填入可编辑文本框。"
    )

    if current_draft and current_draft.strip():
        instruction = (revision_instruction or "").strip() or (
            "在保留现有核心细节和结构的基础上，优化镜头画面感、节奏紧凑度与国际传播感染力。"
        )
        user_prompt = (
            f"【原始创意参考】\n{user_idea}\n\n"
            f"【当前剧本草稿（含用户手改内容，请尊重已有细节）】\n{current_draft.strip()}\n\n"
            f"【本轮修改方向指令】\n{instruction}\n\n"
            "请输出修订后的完整剧本正文。"
        )
    else:
        user_prompt = (
            f"视频总时长：{total_duration} 秒（预计 {recommended_segments} 个片段）。\n"
            f"核心创意与想表达的思想：\n{user_idea}\n\n"
            "请生成包含【核心立意】与【故事脉络】的全片剧本大纲。"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_breakdown_messages(
    *,
    segment_count: int,
    seg_durations: list[int],
    script_draft: str,
    country_names: str,
    cultural_taboos: str,
    db_negative_prompts: str,
    style_template_content: str,
) -> list[dict[str, str]]:
    """构造 Stage 2（执行导演分镜 Agent）的对话消息列表。"""
    duration_lines = "\n".join(
        f"  - 片段{to_cn_index(idx)}（index={idx}）：{dur}秒（时间轴格式：{_timeline_slots_hint(dur)}）"
        for idx, dur in enumerate(seg_durations, start=1)
    )

    system_prompt = (
        "你是一位精通 AI 视频大模型（Seedance / Wanx / Runway）底层提示词工程的“AI 视觉执行导演”。\n"
        f"请将用户确认的剧本，严格拆解为 {segment_count} 个片段，并生成配套的全局设定节点内容。\n\n"
        "【各片段精确时长与时间轴要求】\n"
        f"{duration_lines}\n\n"
        "【注入的跨文化与风格约束】\n"
        f"- 目标传播国家/地区：{country_names}\n"
        f"- 必须规避的文化禁忌：{cultural_taboos}\n"
        f"- 预设负面提示词库：{db_negative_prompts}\n"
        f"- 预设视觉风格参考（若含占位符如 {{subject}}，请提炼其光影、色调、质感与运镜语言融合进整体风格）：\n"
        f"{style_template_content}\n\n"
        "【核心拆解铁律（极其重要）】\n"
        "1. 转换成“AI 视频模型听得懂的语言”：\n"
        "   - 严禁出现心理活动、抽象比喻或旁白说教（例如禁止写“展现出深厚的历史底蕴”）。\n"
        "   - 必须全部转化为【镜头运动 + 主体外观 + 具体物理动作 + 光影变化】。\n"
        "2. 秒级时间轴切分：\n"
        "   - 每个片段必须按对应的时间段明确写出画面动态，例如 15 秒片段格式如下：\n"
        '     "0-5秒：[景别与运镜]，[主体具体动作与环境互动]；\\n'
        "5-10秒：[动作延续或主体状态变化]；\\n"
        '10-15秒：[定格表情、动作收尾或光影转场]。"\n'
        "   - 若该片段分配为 10 秒或 5 秒，则严格按 0-5秒 / 5-10秒 或 0-5秒 切分。\n"
        "3. 角色与场景一致性：\n"
        "   - 在 `image_asset_prompts` 中提炼出供“AI 生图”使用的关键首帧图/参考图提示词，"
        "包含固定的人物外貌、服装与核心场景描述，方便后续各片段保持主体一致。\n"
        "4. 在 `cultural_node_content` 中，必须完整包含目标国家受众建议及合并后的负面提示词（Negative Prompt）。\n"
        "5. 必须只输出一个合法 JSON 对象，禁止 markdown 代码围栏或多余文字，字段严格匹配以下结构：\n"
        "{\n"
        '  "style_node_content": "string",\n'
        '  "cultural_node_content": "string",\n'
        '  "image_asset_prompts": "string",\n'
        '  "segments": [\n'
        "    {\n"
        '      "index": 1,\n'
        '      "title": "片段一",\n'
        '      "duration": 15,\n'
        '      "timeline_prompt": "0-5秒：...\\n5-10秒：...\\n10-15秒：..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"请将以下确认后的剧本严格拆解为 {segment_count} 个连续分镜片段，"
        "确保 `segments` 数组长度严格等于 "
        f"{segment_count}，并输出符合 JSON 结构的对象：\n\n{script_draft}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
