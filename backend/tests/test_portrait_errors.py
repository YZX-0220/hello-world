"""Only explicit image/face admission failures receive the portrait rejection code."""

from unittest.mock import AsyncMock

from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider, _failure, _response_failure
from app.providers.video.base import VideoProviderError
from httpx import Response
from pytest import mark, raises
from respx import get as respx_get
from respx import mock as respx_mock
from respx import post as respx_post

from test_video_adapters import SUBMIT_URL, TASK_URL, _ctx, _request


@mark.parametrize(
    "code,message",
    [
        (
            "InputImageSensitiveContentDetected",
            "The input image contains a real person, which is not supported by this model.",
        ),
        (
            "InputImageSensitiveContentDetected",
            "The request failed because the input image contains a real person.",
        ),
        ("InvalidParameter", "Reference images contain human faces, which are not allowed."),
        ("InputImageSensitiveContentDetected", "Images of real people are not supported."),
        ("HumanFaceRejected", "The supplied material was rejected."),
        ("PortraitPermissionDenied", "Not admitted."),
        ("ImageRejected", "输入图片包含真人，当前模型不支持。"),
        ("ImageRejected", "人像审核失败，请更换素材。"),
    ],
)
def test_explicit_portrait_rejections_keep_vendor_code_in_message(code, message):
    normalized, detail = _failure({"code": code, "message": message})
    assert normalized == "VIDEO_PORTRAIT_REJECTED"
    assert code in detail and message in detail
    assert "未接入专用人像通道" not in detail


@mark.parametrize(
    "code,message",
    [
        ("InvalidParameter", "Unsupported parameter in prompt: images of real people"),
        (
            "InvalidParameter",
            "Unsupported parameter in prompt: images of real people are not supported",
        ),
        ("ContentModeration", "Your portrait prompt was rejected for sensitive content."),
        ("ContentModeration", "Image content failed moderation."),
        ("InsufficientBalance", "Insufficient balance for this portrait generation."),
        ("InsufficientBalance", "Images of real people are not supported. Insufficient balance."),
        ("InvalidParameter", "Portrait aspect ratio is unsupported."),
        ("InvalidParameter", "Invalid prompt: 真人肖像，禁止出现水印。"),
        ("ContentModeration", "图片未通过通用内容审核。"),
        ("InvalidParameter", "Unsupported parameter. A portrait photo was requested."),
    ],
)
def test_prompt_mentions_moderation_and_balance_errors_are_not_portrait_admission(code, message):
    normalized, detail = _failure({"code": code, "message": message})
    assert normalized == code
    assert "VIDEO_PORTRAIT_REJECTED" not in normalized
    assert code in detail


async def test_submit_and_poll_normalize_portrait_errors_without_exposing_signed_urls(monkeypatch):
    monkeypatch.setattr(ArkSeedanceProvider, "_require_public", AsyncMock())
    monkeypatch.setattr(
        "app.providers.video.ark_seedance_v1.validate_public_host", lambda host: None
    )
    vendor = {
        "code": "InputImageSensitiveContentDetected",
        "message": "The input image contains a real person, which is not supported. https://assets.invalid/secret-token Bearer private-key",
    }
    with respx_mock:
        respx_post(SUBMIT_URL).mock(return_value=Response(400, json={"error": vendor}))
        respx_get(TASK_URL).mock(
            return_value=Response(200, json={"status": "failed", "error": vendor})
        )
        with raises(VideoProviderError) as raised:
            await ArkSeedanceProvider().submit(_request(), _ctx())
        assert raised.value.code == "VIDEO_PORTRAIT_REJECTED"
        assert "InputImageSensitiveContentDetected" in raised.value.message
        status = await ArkSeedanceProvider().poll("cgt-1", _ctx())
        assert status.error_code == "VIDEO_PORTRAIT_REJECTED"
        assert "secret-token" not in status.error_message
        assert "private-key" not in status.error_message


def test_non_json_vendor_error_remains_ordinary_submission_failure():
    code, _detail = _response_failure(Response(500, text="portrait"))
    assert code == "VIDEO_SUBMISSION_FAILED"
