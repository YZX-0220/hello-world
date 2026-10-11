"""Prepare a video brief from a fixed selection without modifying the source boxes."""

import json
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import (
    CANVAS_NODE_INVALID,
    CANVAS_VERSION_CONFLICT,
    PROJECT_NOT_CONFIRMED,
    VIDEO_INPUT_INVALID,
    AppError,
)
from app.repositories.projects import ProjectRepository
from app.schemas.agent import VideoBrief
from app.schemas.canvas import CanvasGenerationSettings
from app.services.agent_service import AgentService
from app.services.video_review import REQUIRED_REVIEW_FIELDS, review_markdown


def source_snapshot(data: dict, node_ids: list[str]) -> list[dict[str, Any]]:
    if len(set(node_ids)) != len(node_ids):
        raise AppError(CANVAS_NODE_INVALID, "选择的小框不能重复")
    nodes = data.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}
    if not node_ids or any(nid not in by_id for nid in node_ids):
        raise AppError(CANVAS_NODE_INVALID, "请选择现有的小框")
    ids = set(node_ids)
    for connection in data.get("connections", []):
        for start, end in [("from", "to"), ("to", "from")]:
            if connection[start] in ids:
                linked = by_id.get(connection[end])
                if linked and linked.get("type") == "image" and linked.get("asset_id"):
                    ids.add(linked["id"])
    # Canvas order is deterministic; click order cannot change the resulting video.
    snapshot = []
    for node in nodes:
        if node["id"] not in ids:
            continue
        item = {key: node.get(key) for key in ("id", "type", "title", "content", "asset_id")}
        accepted = node.get("last_ai") or {}
        if accepted.get("brief") and accepted.get("after") == node.get("content"):
            item["confirmed_brief"] = accepted["brief"]
            item["suggested_prompt"] = accepted.get("suggested_prompt")
        snapshot.append(item)
    return snapshot


def validate_generation_sources(project, spec_version: int, requested_ids=None, generation_options=None) -> None:
    data = json.loads(project.canvas_data_json or "{}")
    prepared = data.get("generation_spec_version") == spec_version
    if not prepared:
        if requested_ids:
            raise AppError(PROJECT_NOT_CONFIRMED, "请先整理当前选中小框的视频方案")
        return
    ids = data.get("generation_source_ids", [])
    if requested_ids is not None and (
        not isinstance(requested_ids, list) or any(not isinstance(nid, str) for nid in requested_ids)
    ):
        raise AppError(VIDEO_INPUT_INVALID, "生成来源必须是小框 ID 列表")
    if requested_ids is not None and set(requested_ids) != set(ids):
        raise AppError(PROJECT_NOT_CONFIRMED, "选择的小框已变化，请重新整理视频方案")
    try:
        current = source_snapshot(data, ids)
    except AppError as exc:
        raise AppError(PROJECT_NOT_CONFIRMED, "源小框已删除，请重新整理视频方案") from exc
    if current != data.get("generation_snapshot"):
        raise AppError(PROJECT_NOT_CONFIRMED, "小框内容或关联素材已变化，请重新整理视频方案")
    prepared_settings = data.get("generation_settings")
    if not prepared_settings or prepared_settings != {
        "duration_seconds": data.get("video_duration_seconds"), "resolution": data.get("video_resolution"),
    }:
        raise AppError(PROJECT_NOT_CONFIRMED, "请确认视频时长和清晰度，并重新审理方案")
    options = generation_options or {}
    if generation_options is not None and any(
        options.get(key) != value or type(options.get(key)) is not type(value)
        for key, value in prepared_settings.items()
    ):
        raise AppError(VIDEO_INPUT_INVALID, "提交的时长或清晰度与已审理方案不一致，请重新审理")
    if json.loads(project.current_spec_json or "{}").get("duration_seconds") != prepared_settings["duration_seconds"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "方案时长已变化，请重新审理")


class CanvasVideoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ProjectRepository(session)

    async def prepare(
        self, user_id: str, conversation_id: str, node_ids: list[str], expected_version: int,
        duration_seconds: int, resolution: str,
    ):
        project = await self._repo.get_by_conversation(user_id, conversation_id)
        if project is None:
            raise AppError(CANVAS_NODE_INVALID)
        if project.canvas_version != expected_version:
            raise AppError(CANVAS_VERSION_CONFLICT)
        base_spec_version = project.current_spec_version
        generation_settings = CanvasGenerationSettings.model_validate({"duration_seconds": duration_seconds, "resolution": resolution})
        data = json.loads(project.canvas_data_json or "{}")
        if any(n.get("ai_running") for n in data.get("nodes", [])):
            raise AppError(VIDEO_INPUT_INVALID, "请等待 AI 协作完成，再整理视频方案")
        snapshot = source_snapshot(data, node_ids)
        if any(n["type"] == "video" for n in snapshot):
            raise AppError(VIDEO_INPUT_INVALID, "当前支持选择文本和图片生成；请取消选择视频结果小框")
        if any(n["type"] == "image" and not n["asset_id"] for n in snapshot):
            raise AppError(VIDEO_INPUT_INVALID, "选中的图片尚未上传，请上传图片或取消选择")
        texts = [n for n in snapshot if n["type"] == "text"]
        images = [n["asset_id"] for n in snapshot if n["type"] == "image" and n["asset_id"]]
        if not texts:
            raise AppError(VIDEO_INPUT_INVALID, "请至少选择一个文本小框，可填写想法或留空由 AI 创作")
        if sum(len(n["content"] or "") for n in texts) > 30000:
            raise AppError(VIDEO_INPUT_INVALID, "所选文字超过 30000 字，请减少小框或精简内容")
        inputs = "\n\n".join(
            f"小框【{n['title']}】：\n{n['content'] or '（空白，请自由创作并说明假设）'}"
            + (
                "\n该小框已确认的结构化方案：" + json.dumps(n["confirmed_brief"], ensure_ascii=False)
                + "\n该小框已确认的视频提示词：" + (n.get("suggested_prompt") or "")
                if n.get("confirmed_brief") else ""
            )
            for n in texts
        )
        mode = (
            "first_frame_to_video" if len(images) == 1
            else "reference_image_to_video" if images else "text_to_video"
        )
        asset_spec = VideoBrief.model_validate({
            "mode": mode, "first_frame_asset_id": images[0] if len(images) == 1 else None,
            "reference_asset_ids": images if len(images) > 1 else [],
            "duration_seconds": generation_settings.duration_seconds,
        })
        instruction = (
            "【整理选中小框的视频方案】这些小框共同用于生成一个视频。"
            "以小框当前正文为准，整合为连贯的可执行分镜；不要把文本原样塞进 subject。"
            "保留创作约束，区分镜头运动与主体动作，消除冲突和歧义。"
            "已确认的结构化方案和优化提示词包含正文未展开的创作细节，合并时保留这些细节；"
            "如有含糊或冲突，选择一种符合当前正文与明确限制的实现，并说明取舍，不要提问。"
            "本轮 state_patch 必须是完整方案，提供 subject、scene、camera、motion、lighting、"
            "visual_style、duration_seconds、aspect_ratio；另外给出完整 suggested_prompt。"
            f"【用户确认的生成参数】视频总时长必须为 {duration_seconds} 秒，清晰度为 {resolution}。"
            "本次设置优先于小框中旧的时长描述；按此时长调整分镜和动作时间线并说明调整。"
            "清晰度由系统作为视频 API 参数提交，不要将它写成空泛的风格形容词。"
            "未指定画幅时采用 16:9，默认值会展示给用户。"
            "保持已有素材用途，不要生成素材 ID。"
            "信息不足时补全创作细节并记录 assumptions；用途、受众等可以留空。"
            "suggestions 只提供不阻碍直接生成的可选建议，不要求用户回答或先修改。\n\n"
            + inputs
        )
        agent = AgentService(self._session)
        output = await agent.prepare_video(asset_spec, instruction)
        spec = self._review_spec(output.state_patch.model_dump(exclude_unset=True), asset_spec)
        missing = [field for field in REQUIRED_REVIEW_FIELDS if not getattr(spec, field)]
        if missing:
            # Retry an incomplete model response once, retaining the original text and its constraints.
            # This is model repair, never another user-facing round of questions.
            previous = output
            output = await agent.prepare_video(spec, instruction + (
                "\n\n【补齐输出】上次输出未提供 " + "、".join(missing)
                + "。保留当前方案的已有细节，主动创作补全，返回完整 state_patch，不向用户提问。"
            ))
            patch = {**spec.model_dump(exclude_none=True), **output.state_patch.model_dump(exclude_unset=True)}
            spec = self._review_spec(patch, asset_spec)
            output.assumptions = list(dict.fromkeys(previous.assumptions + output.assumptions))
            if not output.suggestions:
                output.suggestions = previous.suggestions
            output.suggested_prompt = output.suggested_prompt or previous.suggested_prompt
        if not all(getattr(spec, field) for field in REQUIRED_REVIEW_FIELDS):
            raise AppError(VIDEO_INPUT_INVALID, "文本 AI 未完成方案整理，请重新审理；小框内容已保留。")
        # Optional gaps and legacy ready flags are advisory; the executable brief is the gate.
        if not output.state_patch.aspect_ratio and spec.aspect_ratio == "16:9":
            output.assumptions.append("本次默认画幅为 16:9。")
        data.update(
            generation_node_id=texts[0]["id"], generation_source_ids=node_ids,
            generation_snapshot=snapshot, generation_spec_version=base_spec_version + 1,
            generation_review={
                "spec_version": base_spec_version + 1, "content": review_markdown(spec, output, resolution),
            },
            video_duration_seconds=duration_seconds, video_resolution=resolution,
            generation_settings=generation_settings.model_dump(),
        )
        return await self._repo.commit_canvas_spec(
            project, json.dumps(data, ensure_ascii=False), expected_version,
            base_spec_version, spec.model_dump_json(), output.suggested_prompt,
        )

    @staticmethod
    def _review_spec(patch: dict, asset_spec: VideoBrief) -> VideoBrief:
        patch = {key: value for key, value in patch.items() if not key.endswith("asset_id") and key != "reference_asset_ids"}
        return VideoBrief.model_validate({
            **patch, **asset_spec.model_dump(exclude_none=True),
            "duration_seconds": asset_spec.duration_seconds,
            "aspect_ratio": patch.get("aspect_ratio") or "16:9",
            "narration": patch.get("narration") or "无旁白",
        })
