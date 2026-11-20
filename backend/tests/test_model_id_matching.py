"""Model IDs carry a vendor version suffix; matching must survive version bumps."""

from app.core.config import settings
from app.services.video_generation_policy import normalize_model_id, resolve_target


def test_version_suffix_is_removed():
    assert normalize_model_id("doubao-seedance-2-0-fast-260128") == "doubao-seedance-2-0-fast"
    assert normalize_model_id(" doubao-seedance-2-5-flash-261115 ") == "doubao-seedance-2-5-flash"
    assert normalize_model_id("doubao-seedance-2-5") == "doubao-seedance-2-5"
    assert normalize_model_id(None) == ""


async def test_platform_unbound_model_resolves_by_base_name(monkeypatch):
    monkeypatch.setattr(settings, "video_platform_protocol", "ark_seedance_v1")
    monkeypatch.setattr(settings, "video_platform_model", "doubao-seedance-2-0-fast-270101")
    monkeypatch.setattr(settings, "video_platform_profile_code", "")
    target = await resolve_target(None, "probe", "platform")
    assert target.error == ""
    assert target.profile is not None
    assert target.profile.code == "doubao-seedance-2-0-fast"


async def test_bound_profile_must_share_the_same_base_model(monkeypatch):
    monkeypatch.setattr(settings, "video_platform_protocol", "ark_seedance_v1")
    monkeypatch.setattr(settings, "video_platform_model", "doubao-seedance-2-0-fast-270101")
    monkeypatch.setattr(settings, "video_platform_profile_code", "doubao-seedance-2-0-fast")
    target = await resolve_target(None, "probe", "platform")
    assert target.error == ""

    monkeypatch.setattr(settings, "video_platform_profile_code", "doubao-seedance-2-0")
    target = await resolve_target(None, "probe", "platform")
    assert "不一致" in target.error
