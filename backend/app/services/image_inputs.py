"""Read owned image bytes without re-encoding; vendor inputs never use browser URLs."""

import base64
import hashlib
import io

from PIL import Image

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.storage import get_asset_storage

IMAGE_INPUT_INVALID = ErrorCode("IMAGE_INPUT_INVALID", 422, "参考图片不可用")
MAX_REFERENCE_IMAGES = 4


def max_reference_bytes():
    return min(settings.image_max_bytes, 10_000_000)


def inspect_reference(data: bytes, *, formats=("PNG", "JPEG")):
    try:
        if not data or len(data) > max_reference_bytes():
            raise ValueError("图片超过大小上限")
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in formats:
                raise ValueError("请使用 PNG 或 JPEG 图片")
            if (
                im.width <= 14
                or im.height <= 14
                or im.width * im.height > settings.image_max_pixels
            ):
                raise ValueError("图片像素超出范围")
            if not 1 / 16 <= im.width / im.height <= 16:
                raise ValueError("图片宽高比超出范围")
            if getattr(im, "n_frames", 1) != 1:
                raise ValueError("请使用静态图片")
            meta = {
                "width": im.width,
                "height": im.height,
                "mime_type": Image.MIME[im.format] if im.format else "image/png",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
            im.verify()
        # verify() only checks PNG framing; force decoding to reject truncated pixel data.
        with Image.open(io.BytesIO(data)) as im:
            im.load()
        return meta
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise AppError(
            IMAGE_INPUT_INVALID, "参考图需为完整 PNG/JPEG、单张不超过 10 MB，且尺寸符合平台限制。"
        ) from exc


def read_reference(asset, expected_hash=None, *, formats=("PNG", "JPEG")):
    try:
        limit = max_reference_bytes()
        if asset.size_bytes <= 0 or asset.size_bytes > limit:
            raise ValueError("size limit")
        storage = get_asset_storage(asset)
        data = storage.read_bytes(asset.storage_key, max_bytes=limit)
        meta = inspect_reference(data, formats=formats)
        if len(data) != asset.size_bytes or (expected_hash and meta["sha256"] != expected_hash):
            raise ValueError("changed reference")
        if asset.sha256 and len(asset.sha256) == 64 and asset.sha256 != meta["sha256"]:
            raise ValueError("changed asset")
        return data, meta
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            IMAGE_INPUT_INVALID, "参考图片已变化、被删除或无法读取，请重新选择。"
        ) from exc


def data_url(data, mime):
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def compile_edit_prompt(prompt, history):
    if not history:
        return prompt
    # Recent text is context; the latest actual output is always passed as image 1.
    context = "\n".join(f"第{i + 1}轮：{item['prompt'][:600]}" for i, item in enumerate(history))
    return (
        "图片1是选中的上一版结果，请基于它继续修改，未要求改变的主体和细节保持一致。"
        "其他图片（如有）是本轮补充参考。历史描述仅作背景，冲突时以本轮要求为准。\n"
        f"【历史创作要求】\n{context}\n【本轮修改要求】\n{prompt}"
    )
