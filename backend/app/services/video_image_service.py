"""Prepare immutable model inputs while retaining canvas originals.

Only profiles with audited image_constraints opt in. No LLM decides image validity.
Bindings are saved with the review and checked against the actual bytes at submission.
"""

import asyncio
import hashlib
import io
import math

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlmodel import select

from app.core.config import settings
from app.core.errors import PROJECT_NOT_CONFIRMED, AppError
from app.core.ids import new_id
from app.db.models.asset import Asset
from app.repositories.assets import AssetRepository
from app.schemas.agent import VideoBrief
from app.storage import LocalStorage, StorageError
from app.video_registry.models import ImageConstraints


def image_refs(spec: VideoBrief):
    if spec.first_frame_asset_id:
        yield spec.first_frame_asset_id, "first_frame", 0
    if spec.last_frame_asset_id:
        yield spec.last_frame_asset_id, "last_frame", 0
    for i, aid in enumerate(spec.reference_asset_ids):
        yield aid, "reference", i


def _metadata(data, image, mime):
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": image.width,
        "height": image.height,
        "mime_type": mime,
        "size_bytes": len(data),
    }


def image_issues(meta: dict, rules: ImageConstraints) -> list[str]:
    width, height = meta["width"], meta["height"]
    issues = []
    if not (
        rules.min_width <= width <= rules.max_width
        and rules.min_height <= height <= rules.max_height
    ):
        issues.append("图片宽、高必须分别在模型允许的尺寸范围内")
    if height <= 0 or not rules.min_ratio <= width / height <= rules.max_ratio:
        issues.append("图片宽高比超出模型范围")
    if meta["mime_type"] not in rules.mime_types:
        issues.append("图片格式不被当前模型支持")
    if not 0 < meta["size_bytes"] < rules.max_bytes_exclusive:
        issues.append("图片文件大小超出模型范围")
    return issues


def _open(data):
    image = Image.open(io.BytesIO(data))
    if image.width * image.height > settings.image_max_pixels:
        image.close()
        raise ValueError("图片超过平台解码像素上限，请缩小后上传")
    image.load()  # Reject truncated/corrupt images, not just a plausible header.
    return image


def adapt_image(data: bytes, rules: ImageConstraints):
    """Resize proportionally; use neutral padding instead of cropping/distortion."""
    actions = []
    with _open(data) as source:
        mime = Image.MIME.get(source.format, "")
        animated = getattr(source, "n_frames", 1) > 1
        if animated:
            source.seek(0)
            actions.append("提取第一帧作为静态参考图")
        orientation = source.getexif().get(274, 1)
        image = ImageOps.exif_transpose(source)
        if orientation in range(2, 9):
            actions.append("按图片方向信息纠正旋转或镜像")
        width, height = image.size
        canvas_w = max(width, math.ceil(height * rules.min_ratio))
        canvas_h = max(height, math.ceil(width / rules.max_ratio))
        upper = min(
            rules.max_width / canvas_w,
            rules.max_height / canvas_h,
            math.sqrt(settings.image_max_pixels / (canvas_w * canvas_h)),
        )
        lower = max(rules.min_width / canvas_w, rules.min_height / canvas_h)
        scale = max(lower, min(1.0, upper))
        if scale != 1:
            # Leave rounding headroom at the upper pixel boundary.
            if scale < 1:
                scale *= 0.999
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
            actions.append(
                f"等比{'放大' if scale > 1 else '缩小'}：{width}×{height} → {image.width}×{image.height}"
            )
        canvas_w = max(image.width, rules.min_width, math.ceil(image.height * rules.min_ratio))
        canvas_h = max(image.height, rules.min_height, math.ceil(image.width / rules.max_ratio))
        padding = (canvas_w, canvas_h) != image.size
        needs_conversion = mime not in ("image/jpeg", "image/png", "image/webp") or animated
        if padding or needs_conversion or actions or len(data) >= rules.max_bytes_exclusive:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", (canvas_w, canvas_h), (24, 24, 24))
            background.paste(
                rgba, ((canvas_w - rgba.width) // 2, (canvas_h - rgba.height) // 2), rgba
            )
            if padding:
                actions.append(f"背景补边至 {canvas_w}×{canvas_h}，保留完整画面，不裁剪主体")
            if "A" in image.getbands() or image.info.get("transparency") is not None:
                actions.append("透明区域填充深灰色背景")
            if mime != "image/jpeg" or animated:
                actions.append("转换为 JPEG 格式")
            for quality in (92, 85, 75, 60):
                stream = io.BytesIO()
                background.save(stream, format="JPEG", quality=quality, optimize=True)
                encoded = stream.getvalue()
                if len(encoded) < rules.max_bytes_exclusive:
                    break
            if len(data) >= rules.max_bytes_exclusive:
                actions.append("压缩图片文件大小")
            meta = _metadata(encoded, background, "image/jpeg")
        else:
            encoded = data
            meta = _metadata(data, image, mime)
        errors = image_issues(meta, rules)
        if errors or meta["width"] * meta["height"] > settings.image_max_pixels:
            raise ValueError("图片无法自动适配，请换用尺寸和画幅适中的图片")
        return encoded, meta, actions


def _read_asset(asset, storage):
    path = storage.open_read_path(asset.storage_key)
    if path.stat().st_size != asset.size_bytes or path.stat().st_size >= 30_000_000:
        raise ValueError("素材文件大小已变化或超出处理范围，请重新上传")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != asset.sha256:
        raise ValueError("素材文件内容已变化，请重新上传")
    return data


def _cached_matches(asset, storage, meta):
    try:
        return all(getattr(asset, k) == v for k, v in meta.items()) and bool(
            _read_asset(asset, storage)
        )
    except (OSError, ValueError, StorageError):
        return False


def _inspect_bytes(data):
    with _open(data) as image:
        return _metadata(data, image, Image.MIME.get(image.format, ""))


async def prepare_images(session, user_id, profile, spec, titles, pending=None):
    rules = profile.image_constraints if profile else None
    if rules is None:
        return [], [], [], []
    storage = LocalStorage(settings.storage_root)
    repo = AssetRepository(session)
    bindings, notices, issues, cache = [], [], [], {}
    if pending is None:
        pending = []
    for source_id, role, position in image_refs(spec):
        title = titles.get(source_id, "图片")
        try:
            if source_id not in cache:
                source = await repo.get_for_user(source_id, user_id)
                if source is None or source.status != "ready" or source.kind != "image":
                    raise ValueError("素材不存在、未就绪或无权使用，请重新上传")
                data = await asyncio.to_thread(_read_asset, source, storage)
                encoded, meta, actions = await asyncio.to_thread(adapt_image, data, rules)
                prepared = source
                if any(getattr(source, k) != v for k, v in meta.items()):
                    # Reuse identical derived bytes owned by this user; never infer cross-user files.
                    prepared = (
                        await session.exec(
                            select(Asset).where(
                                Asset.user_id == user_id,
                                Asset.sha256 == meta["sha256"],
                                Asset.purpose == "generation_input",
                                Asset.status == "ready",
                            )
                        )
                    ).first()
                    if prepared is None or not await asyncio.to_thread(
                        _cached_matches, prepared, storage, meta
                    ):
                        aid = new_id()
                        ext = {"image/png": "png", "image/webp": "webp"}.get(
                            meta["mime_type"], "jpg"
                        )
                        key = f"{user_id}/generation-input/{aid}.{ext}"
                        await asyncio.to_thread(storage.write_stream, encoded, key, final_key=key)
                        prepared = Asset(
                            id=aid,
                            user_id=user_id,
                            conversation_id=source.conversation_id,
                            kind="image",
                            purpose="generation_input",
                            original_name="生成用适配图片.jpg",
                            storage_key=key,
                            status="ready",
                            **meta,
                        )
                        # Do not hold a database write lock while the text AI is running.
                        pending.append(prepared)
                cache[source_id] = source, prepared, meta, actions
                if actions:
                    notices.append(f"图片【{title}】：{'；'.join(actions)}。原图已保留。")
                    if any("放大" in action for action in actions):
                        notices.append(
                            f"图片【{title}】的放大用于满足输入尺寸，不会恢复原图缺失的细节。"
                        )
            source, prepared, meta, actions = cache[source_id]
            bindings.append(
                {
                    "source_asset_id": source_id,
                    "source_sha256": source.sha256,
                    "asset_id": prepared.id,
                    "role": role,
                    "position": position,
                    **meta,
                    "actions": actions,
                }
            )
        except (
            OSError,
            ValueError,
            StorageError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ):
            issues.append(f"图片【{title}】无法读取或自动适配，请换图或重新上传后审理。")
    return bindings, notices, issues, pending


def apply_image_bindings(spec, bindings):
    values = spec.model_dump()
    for binding in bindings:
        if binding["role"] == "reference":
            values["reference_asset_ids"][binding["position"]] = binding["asset_id"]
        else:
            values[f"{binding['role']}_asset_id"] = binding["asset_id"]
    return VideoBrief.model_validate(values)


async def validate_review_images(session, user_id, profile, spec, bindings):
    rules = profile.image_constraints if profile else None
    if rules is None:
        return
    expected = list(image_refs(spec))
    actual = [(b["asset_id"], b["role"], b["position"]) for b in bindings]
    if actual != expected:
        raise AppError(PROJECT_NOT_CONFIRMED, "生成素材未绑定本次审理，请重新审理。")
    repo, storage = AssetRepository(session), LocalStorage(settings.storage_root)
    checked = set()
    for binding in bindings:
        try:
            for aid, sha in (
                (binding["source_asset_id"], binding["source_sha256"]),
                (binding["asset_id"], binding["sha256"]),
            ):
                row = await repo.get_for_user(aid, user_id)
                if row is None or row.status != "ready" or row.kind != "image" or row.sha256 != sha:
                    raise ValueError("素材已变化")
                if aid not in checked:
                    data = await asyncio.to_thread(_read_asset, row, storage)
                    checked.add(aid)
                else:
                    data = None
                if aid == binding["asset_id"] and data is not None:
                    meta = await asyncio.to_thread(_inspect_bytes, data)
                    if any(meta[k] != binding[k] for k in meta) or image_issues(meta, rules):
                        raise ValueError("素材不符合审理快照或模型要求")
        except (
            OSError,
            ValueError,
            StorageError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ) as exc:
            raise AppError(
                PROJECT_NOT_CONFIRMED, "审理所用图片已失效或变化，请重新上传或重新审理。"
            ) from exc
