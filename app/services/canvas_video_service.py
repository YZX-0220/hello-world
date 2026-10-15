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
from app.schemas.agent import AgentOutput, VideoBrief
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
                if linked and linked.get("type") == "image":
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


def validate_generation_sources(
    project,
    spec_version: int,
    requested_ids=None,
    generation_options=None,
    record: dict | None = None,
) -> None:
    data = json.loads(project.canvas_data_json or "{}")
    if record is None:
        if data.get("generation_spec_version") == spec_version:
            raise AppError(PROJECT_NOT_CONFIRMED, "旧版审理未绑定模型，请重新点击“AI审理方案”。")
        if requested_ids:
            raise AppError(PROJECT_NOT_CONFIRMED, "请先审理当前选中的小框。")
        return
    if record["status"] != "ready":
        raise AppError(PROJECT_NOT_CONFIRMED, "当前审理尚不能生成，请按审理结果调整后重试。")
    ids = record["source_ids"]
    if requested_ids is not None and (
        not isinstance(requested_ids, list)
        or any(not isinstance(n, str) for n in requested_ids)
        or set(requested_ids) != set(ids)
    ):
        raise AppError(PROJECT_NOT_CONFIRMED, "选择的小框已变化，请重新审理。")
    try:
        snapshot = source_snapshot(data, ids)
    except AppError as exc:
        raise AppError(PROJECT_NOT_CONFIRMED, "来源小框已变化，请重新审理。") from exc
    if snapshot != record["sources"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "小框内容或关联素材已变化，请重新审理。")
    requested = {
        "duration_seconds": data.get("video_duration_seconds"),
        "resolution": data.get("video_resolution"),
    }
    if requested != record["requested_settings"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "时长或清晰度已变化，请重新审理。")
    if {
        "mode": data.get("video_mode", "auto"),
        "input_roles": data.get("video_input_roles", {}),
    } != record["input"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "生成模式或素材角色已变化，请重新审理。")
    if data.get("selected_api_config_id", "platform") != record["target"]["api_config_id"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "生成通道已变化，请重新审理。")
    if (
        data.get("generation_spec_version") != spec_version
        or data.get("generation_settings") != record["settings"]
    ):
        raise AppError(PROJECT_NOT_CONFIRMED, "生成方案记录已变化，请重新审理。")
    if generation_options is not None:
        for key, value in record["settings"].items():
            if generation_options.get(key) != value or type(
                generation_options.get(key)
            ) is not type(value):
                raise AppError(VIDEO_INPUT_INVALID, "提交参数与展示的审理方案不一致，请重新审理。")
        if generation_options.get("review_fingerprint") != record["fingerprint"]:
            raise AppError(PROJECT_NOT_CONFIRMED, "提交的审理版本不一致，请重新审理。")


async def reviewed_version(
    session, project, version: int, *, config_id=None, requested_ids=None, options=None
):
    from sqlmodel import select

    from app.db.models.project import VideoProjectVersion
    from app.services.video_generation_policy import resolve_target, validate_settings

    row = (
        await session.exec(
            select(VideoProjectVersion).where(
                VideoProjectVersion.project_id == project.id,
                VideoProjectVersion.version == version,
            )
        )
    ).first()
    if row is None or not row.generation_review_json:
        raise AppError(
            PROJECT_NOT_CONFIRMED, "当前方案尚未进行模型适配审理，请重新点击“AI审理方案”。"
        )
    record = json.loads(row.generation_review_json)
    if version != project.current_spec_version or json.loads(row.spec_json) != json.loads(
        project.current_spec_json
    ):
        raise AppError(PROJECT_NOT_CONFIRMED, "方案版本已变化，请重新审理。")
    validate_generation_sources(project, version, requested_ids, options, record)
    if config_id is not None and config_id != record["target"]["api_config_id"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "提交通道与审理通道不同，请重新审理。")
    target = await resolve_target(session, project.user_id, record["target"]["api_config_id"])
    if target.error or target.fingerprint != record["target"]["fingerprint"]:
        raise AppError(PROJECT_NOT_CONFIRMED, "模型配置或能力规则已更新，请重新审理。")
    spec = VideoBrief.model_validate(json.loads(row.spec_json))
    validate_settings(target, spec, record["settings"], record["wire"])
    return row, record, target


async def restore_review_metadata(session, project, data):
    """Canvas writes cannot replace server-authored plans, parameters or review text."""
    from sqlmodel import select

    from app.db.models.project import VideoProjectVersion

    row = (
        await session.exec(
            select(VideoProjectVersion).where(
                VideoProjectVersion.project_id == project.id,
                VideoProjectVersion.version == project.current_spec_version,
            )
        )
    ).first()
    if row is not None and row.generation_review_json:
        record = json.loads(row.generation_review_json)
        data.update(
            generation_spec_version=record["spec_version"],
            generation_source_ids=record["source_ids"],
            generation_node_id=next(n["id"] for n in record["sources"] if n["type"] == "text"),
            generation_snapshot=record["sources"],
            generation_requested_settings=record["requested_settings"],
            generation_settings=record["settings"],
            generation_target=record["target"],
            generation_input=record["input"],
            generation_review={
                "spec_version": record["spec_version"],
                "content": record["content"],
                "status": record["status"],
                "fingerprint": record["fingerprint"],
                "issues": record["issues"],
            },
        )
    else:
        data.update(
            generation_spec_version=0,
            generation_source_ids=[],
            generation_node_id="",
            generation_snapshot=[],
            generation_review=None,
            generation_settings=None,
            generation_requested_settings=None,
            generation_target=None,
            generation_input=None,
        )
    return data


def _asset_spec(snapshot, mode, roles, duration):
    images = [n for n in snapshot if n["type"] == "image" and n["asset_id"]]
    if mode == "auto":
        mode = (
            "first_frame_to_video"
            if len(images) == 1
            else "reference_image_to_video"
            if images
            else "text_to_video"
        )
    values = {"mode": mode, "duration_seconds": duration}
    issues = []
    if mode == "first_frame_to_video":
        if len(images) == 1:
            values["first_frame_asset_id"] = images[0]["asset_id"]
        else:
            issues.append("首帧模式需要且只使用一张图片，请调整选中或关联的图片。")
    elif mode == "first_last_frame_to_video":
        by_id = {n["id"]: n["asset_id"] for n in images}
        first = roles.get("first_frame_node_id") or (images[0]["id"] if images else "")
        last = roles.get("last_frame_node_id") or (images[1]["id"] if len(images) > 1 else "")
        if len(images) != 2 or first == last or first not in by_id or last not in by_id:
            issues.append("首尾帧模式需要两张不同的图片，请选择首帧和尾帧。")
        else:
            values.update(first_frame_asset_id=by_id[first], last_frame_asset_id=by_id[last])
    elif mode == "reference_image_to_video":
        values["reference_asset_ids"] = [n["asset_id"] for n in images]
    elif mode == "text_to_video" and images:
        issues.append("选中的小框包含图片。请使用图生视频模式，或取消所选、关联的图片。")
    return VideoBrief.model_validate(values), issues


def _creative_spec(patch, asset_spec, effective):
    # All material roles and technical parameters are owned by the deterministic policy.
    technical = {"mode", "duration_seconds", "aspect_ratio", "reference_asset_ids"}
    clean = {k: v for k, v in patch.items() if k not in technical and not k.endswith("asset_id")}
    for key in (
        "mode",
        "first_frame_asset_id",
        "last_frame_asset_id",
        "reference_asset_ids",
        "source_video_asset_id",
        "audio_asset_id",
    ):
        clean[key] = getattr(asset_spec, key)
    clean.update(
        duration_seconds=effective["duration_seconds"], aspect_ratio=effective["aspect_ratio"]
    )
    clean["narration"] = clean.get("narration") or "无旁白"
    import re

    ratio = effective["aspect_ratio"]
    ratio_pattern = (
        r"(?<![\d:：])(?:[1-9]|[12][0-9]|3[0-2])\s*[:：]\s*(?:[1-9]|[12][0-9]|3[0-2])(?![\d:：])"
    )
    for key in (*REQUIRED_REVIEW_FIELDS, "objective", "audience", "narration", "negative_prompt"):
        if isinstance(clean.get(key), str):
            clean[key] = re.sub(
                ratio_pattern, "随素材自适应" if ratio == "adaptive" else ratio, clean[key]
            )
            clean[key] = re.sub(
                r"(?<![A-Za-z0-9])(?:480|580|720|1080|1440|2160)[pP](?![A-Za-z0-9])",
                effective["resolution"],
                clean[key],
            )
    return VideoBrief.model_validate(clean)


def _timing_issues(spec):
    import re

    for key in REQUIRED_REVIEW_FIELDS:
        for value in re.findall(r"(?<!\d)(\d+(?:\.\d+)?)\s*秒", getattr(spec, key) or ""):
            if float(value) > spec.duration_seconds:
                return ["画面描述中的动作时间线超过最终总时长，请压缩到最终时长内。"]
    return []


class CanvasVideoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ProjectRepository(session)

    async def prepare(
        self,
        user_id,
        conversation_id,
        node_ids,
        expected_version,
        duration_seconds,
        resolution,
        api_config_id="platform",
        mode="auto",
        input_roles=None,
    ):
        import re

        from app.services.video_generation_policy import digest, propose_settings, resolve_target
        from app.services.video_prompt import compile_video_prompt

        roles = input_roles or {}
        project = await self._repo.get_by_conversation(user_id, conversation_id)
        if project is None:
            raise AppError(CANVAS_NODE_INVALID)
        if project.canvas_version != expected_version:
            raise AppError(CANVAS_VERSION_CONFLICT)
        base_version = project.current_spec_version
        requested = CanvasGenerationSettings(
            duration_seconds=duration_seconds, resolution=resolution
        ).model_dump()
        data = json.loads(project.canvas_data_json or "{}")
        if any(n.get("ai_running") for n in data.get("nodes", [])):
            raise AppError(VIDEO_INPUT_INVALID, "请等待 AI 协作完成，再审理方案。")
        snapshot = source_snapshot(data, node_ids)
        texts = [n for n in snapshot if n["type"] == "text"]
        if not texts:
            raise AppError(
                VIDEO_INPUT_INVALID, "请至少选择一个文本小框，可填写想法或留空由 AI 创作。"
            )
        if sum(len(n["content"] or "") for n in texts) > 30000:
            raise AppError(VIDEO_INPUT_INVALID, "所选文字超过 30000 字，请精简内容。")
        issues = []
        if any(n["type"] == "video" for n in snapshot):
            issues.append("当前画布入口支持文本和图片生成，请取消选择视频结果小框。")
        if any(n["type"] == "image" and not n["asset_id"] for n in snapshot):
            issues.append("选中的图片尚未上传，请上传图片或取消选择。")
        for node in snapshot:
            if node.get("asset_id"):
                from app.repositories.assets import AssetRepository

                asset = await AssetRepository(self._session).get_for_user(node["asset_id"], user_id)
                if asset is None or asset.status != "ready" or asset.kind != "image":
                    issues.append("选中的图片素材不存在、未就绪或无权使用，请重新上传。")
        target = await resolve_target(self._session, user_id, api_config_id)
        asset_spec, role_issues = _asset_spec(snapshot, mode, roles, duration_seconds)
        issues.extend(role_issues)
        inputs = "\n\n".join(
            f"小框【{n['title']}】：\n{n['content'] or '（空白，请自由创作并说明假设）'}"
            + (
                "\n该小框已确认的结构化方案："
                + json.dumps(n["confirmed_brief"], ensure_ascii=False)
                + "\n该小框已确认的视频提示词："
                + (n.get("suggested_prompt") or "")
                if n.get("confirmed_brief")
                else ""
            )
            for n in texts
        )
        ratios = re.findall(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)", inputs)
        requested_ratio = next((f"{a}:{b}" for a, b in ratios if int(a) and int(b)), None)
        proposal = propose_settings(
            target,
            asset_spec,
            {**requested, "aspect_ratio": requested_ratio, "generate_audio": True},
        )
        issues.extend(proposal["issues"])
        effective = proposal["settings"]
        changes = proposal["changes"]
        output = AgentOutput()
        spec = asset_spec
        if not issues:
            instruction = (
                "【整理选中小框的视频方案】这些小框共同用于生成一个视频。"
                "以当前正文为准，整合为连贯可执行的方案；保留主体、场景、运镜限制，区分镜头与主体动作。"
                "参考已确认结构中的创作细节，但忽略与本次技术参数冲突的旧画幅、时长和清晰度。"
                "不向用户提问、不索要确认；信息不足时创作补全，并说明假设。"
                "state_patch 必须提供完整 subject、scene、camera、motion、lighting、visual_style。"
                f"视频总时长必须为 {effective['duration_seconds']} 秒，清晰度为 {effective['resolution']}。"
                f"画幅为 {effective['aspect_ratio']}；声音生成：{effective['generate_audio']}。"
                "所有动作时间线必须处于最终总时长内。不在创作字段重复技术参数，禁止承诺其他画幅。"
                "suggestions 仅为可选建议，不作为生成前提。素材 ID、生成模式由系统固定。"
                "\n【模型及模式规则】"
                + json.dumps(target.view(), ensure_ascii=False, default=str)
                + "\n【本次参数调整】"
                + json.dumps(changes, ensure_ascii=False)
                + "\n\n"
                + inputs
            )
            agent = AgentService(self._session)
            patch = {}
            assumptions = []
            suggestions = []
            for _attempt in range(2):
                output = await agent.prepare_video(asset_spec, instruction)
                assumptions.extend(output.assumptions)
                suggestions.extend(output.suggestions)
                patch.update(output.state_patch.model_dump(exclude_unset=True))
                spec = _creative_spec(patch, asset_spec, effective)
                missing = [k for k in REQUIRED_REVIEW_FIELDS if not getattr(spec, k)]
                timing = _timing_issues(spec)
                if not missing and not timing:
                    break
                instruction += (
                    "\n【补齐输出】主动补全 "
                    + "、".join(missing)
                    + "；"
                    + " ".join(timing)
                    + "不要提问。上一轮方案："
                    + spec.model_dump_json()
                )
            if missing or timing:
                issues.append(
                    "文本 AI 未完成合法的画面描述与动作时间线，请重新审理；原始小框已保留。"
                )
            # The displayed fields are the sole compiled prompt source. Free-form AI prompt
            # is intentionally not concatenated: it may carry obsolete technical settings.
            output.suggested_prompt = None
            output.assumptions = [
                n
                for n in dict.fromkeys(assumptions)
                if not re.search(r"\d+\s*[:：]\s*\d+|\d+\s*秒|\d+p|[？?]", n)
            ][:5]
            output.suggestions = [
                n
                for n in dict.fromkeys(suggestions)
                if not re.search(r"[？?]|需要你确认|请.*回答|\d+\s*[:：]\s*\d+|\d+\s*秒|\d+p", n)
            ][:3]
            if spec.first_frame_asset_id:
                title = next(
                    n["title"] for n in snapshot if n["asset_id"] == spec.first_frame_asset_id
                )
                output.assumptions.append(f"首帧使用小框【{title}】的图片。")
            if spec.last_frame_asset_id:
                title = next(
                    n["title"] for n in snapshot if n["asset_id"] == spec.last_frame_asset_id
                )
                output.assumptions.append(f"尾帧使用小框【{title}】的图片。")
            if not requested_ratio and effective["aspect_ratio"] != "adaptive":
                output.assumptions.append(f"本次默认画幅为 {effective['aspect_ratio']}。")
        # Detect target revision/rule changes during the LLM call as well as canvas edits.
        current_target = await resolve_target(self._session, user_id, api_config_id)
        if current_target.fingerprint != target.fingerprint:
            raise AppError(CANVAS_VERSION_CONFLICT, "审理期间模型配置已更新，请重新审理。")
        status = "blocked" if issues else "ready"
        content = review_markdown(
            spec,
            output,
            effective.get("resolution", resolution),
            target=target.snapshot(),
            changes=changes,
            issues=issues,
        )
        record = {
            "status": status,
            "target": target.snapshot(),
            "sources": snapshot,
            "source_ids": node_ids,
            "requested_settings": requested,
            "settings": effective,
            "wire": proposal["wire"],
            "input": {"mode": mode, "input_roles": roles},
            "changes": changes,
            "issues": issues,
            "content": content,
            "spec_version": base_version + 1,
            "compiled_prompt": compile_video_prompt(spec) if status == "ready" else "",
        }
        record["fingerprint"] = digest(record)
        data.update(
            generation_node_id=texts[0]["id"],
            generation_source_ids=node_ids,
            generation_snapshot=snapshot,
            generation_spec_version=base_version + 1,
            generation_review={
                "spec_version": base_version + 1,
                "content": content,
                "status": status,
                "fingerprint": record["fingerprint"],
                "issues": issues,
            },
            generation_requested_settings=requested,
            generation_settings=effective,
            generation_target=target.snapshot(),
            generation_input=record["input"],
            video_mode=mode,
            video_input_roles=roles,
            video_duration_seconds=duration_seconds,
            video_resolution=resolution,
            selected_api_config_id=api_config_id,
        )
        return await self._repo.commit_canvas_spec(
            project,
            json.dumps(data, ensure_ascii=False),
            expected_version,
            base_version,
            spec.model_dump_json(),
            None,
            json.dumps(record, ensure_ascii=False),
        )
