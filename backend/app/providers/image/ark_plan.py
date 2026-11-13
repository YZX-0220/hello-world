"""Ark image adapter. A frozen model ID selects its endpoint; never cross-route on failure."""

from asyncio import to_thread
from base64 import b64decode
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from logging import getLogger
from urllib.parse import urlsplit

from httpx import AsyncClient, HTTPError
from PIL import Image, ImageDraw

from app.core.config import settings
from app.core.ssrf import validate_public_host

logger = getLogger(__name__)

ENDPOINT = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
STANDARD_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
MODELS = [
    {"id": "doubao-seedream-5-0-pro-260628", "label": "Seedream 5.0 Pro", "api_type": "standard"},
    {
        "id": "doubao-seedream-5-0-flash-260915",
        "label": "Seedream 5.0 Flash",
        "api_type": "standard",
    },
    {"id": "doubao-seedream-5.0-pro", "label": "Seedream 5.0 Pro", "api_type": "subscription"},
    {"id": "doubao-seedream-5.0-flash", "label": "Seedream 5.0 Flash", "api_type": "subscription"},
]
SIZES = {
    "1:1": "1536x1536",
    "16:9": "2048x1152",
    "9:16": "1152x2048",
    "4:3": "1792x1344",
    "3:4": "1344x1792",
}


@dataclass
class ImageResult:
    url: str | None = None
    data: bytes | None = None
    request_id: str | None = None


class ImageProviderError(Exception):
    def __init__(self, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


async def generate_image(
    *,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
    images: list[str] | None = None,
    watermark: bool = False,
) -> ImageResult:
    selected = next((item for item in MODELS if item["id"] == model), None)
    if selected is None:
        raise ImageProviderError("当前生图模型暂不可用，请重新选择图片 API。")
    endpoint = STANDARD_ENDPOINT if selected["api_type"] == "standard" else ENDPOINT
    status = None
    content_type = None
    response_size = 0
    try:
        async with (
            AsyncClient(
                timeout=settings.image_timeout_seconds, trust_env=False, follow_redirects=False
            ) as client,
            client.stream(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "response_format": settings.image_response_format,
                    "output_format": "png",
                    "watermark": watermark,
                    **({"image": images} if images else {}),
                },
            ) as response,
        ):
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            if response.status_code >= 500:
                raise ImageProviderError(
                    "生图服务响应异常，提交结果待确认；请先在方舟控制台核对，勿重复提交。",
                    uncertain=True,
                )
            if response.status_code != 200:
                messages = {
                    401: "图片 API 密钥无效或密钥类型不匹配，请检查配置。",
                    403: "当前密钥没有模型使用权限。",
                    404: "当前模型不存在或尚未开通，请检查所选模型与密钥类型。",
                    429: "可用额度或调用频率受限，请稍后重试或检查方舟控制台。",
                }
                raise ImageProviderError(
                    messages.get(
                        response.status_code, "生图请求未被接受，请检查模型、描述及使用权限。"
                    )
                )
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                response_size = len(raw)
                if len(raw) > settings.image_max_result_bytes * 4 // 3 + 65536:
                    raise ImageProviderError(
                        "生图响应超出接收上限，请在方舟控制台核对结果。", uncertain=True
                    )
            from json import loads as json_loads

            payload = json_loads(raw)
            items = payload.get("data") or []
            if not items or not isinstance(items[0], dict):
                raise ImageProviderError(
                    "生图服务未返回图片，请在方舟控制台核对结果。", uncertain=True
                )
            item = items[0]
            rid = response.headers.get("x-request-id") or payload.get("request_id")
            if item.get("url"):
                return ImageResult(url=item["url"], request_id=rid)
            if item.get("b64_json"):
                return ImageResult(data=b64decode(item["b64_json"], validate=True), request_id=rid)
            raise ImageProviderError("生图服务未返回可保存的图片，请核对结果。", uncertain=True)
    except ImageProviderError:
        raise
    except (HTTPError, ValueError, KeyError, TypeError) as exc:
        # Never log credentials, request bodies or signed image URLs.
        logger.warning(
            "Image request failed: error=%s status=%s content_type=%s response_bytes=%s",
            type(exc).__name__,
            status,
            content_type,
            response_size,
        )
        # A timeout cannot prove that the vendor did not charge/generate. Never auto-resubmit.
        raise ImageProviderError(
            "连接中断或返回内容无法识别，生成结果待确认；请先在方舟控制台核对。", uncertain=True
        ) from exc


async def download_image(url: str) -> bytes:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    allowed = ("volces.com", "volccdn.com", "byteimg.com", "volcengine.com")
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not any(host == suffix or host.endswith("." + suffix) for suffix in allowed)
    ):
        raise ValueError("生图结果不是受支持的方舟 HTTPS 文件地址")
    await to_thread(validate_public_host, host)
    async with (
        AsyncClient(timeout=60, trust_env=False, follow_redirects=False) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > settings.image_max_result_bytes:
                raise ValueError("图片文件超过保存上限")
    return bytes(data)


def fake_image(prompt: str, size: str) -> bytes:
    """A clearly marked local fixture, never represented as an AI or trusted portrait output."""
    width, height = map(int, size.split("x"))
    digest = sha256(prompt.encode()).digest()
    im = Image.new("RGB", (width, height), (23, 30, 48))
    draw = ImageDraw.Draw(im)
    for index in range(7):
        x = int(width * (index + 1) / 9)
        y = int(height * (0.25 + digest[index] / 1024))
        r = min(width, height) // 8
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(70 + digest[index] // 2, 105, 170))
    draw.rounded_rectangle(
        (width * 0.08, height * 0.7, width * 0.92, height * 0.9), radius=20, fill=(35, 45, 66)
    )
    draw.text(
        (width * 0.12, height * 0.74),
        "LOCAL SIMULATION - NOT AI GENERATED",
        fill="white",
        font_size=max(18, width // 40),
    )
    draw.text(
        (width * 0.12, height * 0.82),
        f"{size}  /  {sha256(prompt.encode()).hexdigest()[:12]}",
        fill="white",
        font_size=max(16, width // 50),
    )
    output = BytesIO()
    im.save(output, "PNG")
    return output.getvalue()
