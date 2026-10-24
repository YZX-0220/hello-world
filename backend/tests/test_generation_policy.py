import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.core.errors import AppError
from app.schemas.agent import VideoBrief
from app.services.video_generation_policy import (
    GenerationTarget,
    propose_settings,
    validate_settings,
)
from app.video_registry import get_profile
from app.video_registry.models import ModeConstraint, ParameterRule


def target(profile):
    return GenerationTarget({"remote_model_id": profile.remote_model_id}, "测试通道", profile)


def requested(**changes):
    return {
        "duration_seconds": 8,
        "resolution": "1080p",
        "aspect_ratio": "16:9",
        "generate_audio": True,
        **changes,
    }


@pytest.mark.parametrize("mode", ["first_frame_to_video", "first_last_frame_to_video"])
def test_adaptive_ratio_is_a_visible_change_and_omitted_on_wire(mode):
    profile = get_profile("ark_seedance_v1", "doubao-seedance-2-5")
    spec = VideoBrief(
        mode=mode,
        first_frame_asset_id="first",
        last_frame_asset_id="last" if mode == "first_last_frame_to_video" else None,
    )
    result = propose_settings(target(profile), spec, requested())
    assert not result["issues"]
    assert result["settings"]["aspect_ratio"] == "adaptive"
    assert "aspect_ratio" not in result["wire"]
    assert any(c["before"] == "16:9" and c["after"] == "adaptive" for c in result["changes"])
    validate_settings(target(profile), spec, result["settings"], result["wire"])


def test_rules_are_general_and_choose_a_legal_parameter_combination():
    profile = replace(
        get_profile("ark_seedance_v1", "doubao-seedance-2-0"),
        rules=(
            ParameterRule(
                "duration_seconds",
                maximum=5,
                when={"resolution": "1080p"},
                note="测试规则：高清最多五秒。",
            ),
        ),
    )
    result = propose_settings(target(profile), VideoBrief(mode="text_to_video"), requested())
    assert not result["issues"]
    assert not (
        result["settings"]["resolution"] == "1080p" and result["settings"]["duration_seconds"] > 5
    )
    validate_settings(
        target(profile), VideoBrief(mode="text_to_video"), result["settings"], result["wire"]
    )
    with pytest.raises(AppError):
        validate_settings(
            target(profile), VideoBrief(mode="text_to_video"), requested(), requested()
        )


@pytest.mark.parametrize("code", ["wan2.5-t2v-preview", "wan2.2-t2v-plus"])
def test_other_protocols_adapt_duration_and_audio_before_submission(code):
    profile = get_profile("dashscope_async_v1", code)
    result = propose_settings(
        target(profile), VideoBrief(mode="text_to_video"), requested(duration_seconds=8)
    )
    assert result["settings"]["duration_seconds"] == 10
    assert result["settings"]["generate_audio"] is False
    assert "generate_audio" not in result["wire"]
    assert {c["field"] for c in result["changes"]} >= {"duration_seconds", "generate_audio"}


def test_mode_specific_duration_omission_is_disclosed_and_not_confused_with_requested_duration():
    profile = replace(
        get_profile("ark_seedance_v1", "doubao-seedance-2-0"),
        mode_constraints=(ModeConstraint("text_to_video", duration="omit"),),
    )
    result = propose_settings(
        target(profile), VideoBrief(mode="text_to_video"), requested(duration_seconds=7)
    )
    assert result["settings"]["duration_seconds"] == 7
    assert "duration_seconds" not in result["wire"]
    assert any(c["field"] == "duration_transport" for c in result["changes"])


@pytest.mark.parametrize(
    "kind", ["unknown", "unsupported", "too_many_images", "duplicate_roles", "fixed_duration"]
)
def test_unresolvable_inputs_block_without_discarding_materials(kind):
    profile = get_profile("ark_seedance_v1", "doubao-seedance-2-5")
    spec = VideoBrief(mode="text_to_video")
    selected = target(profile)
    if kind == "unknown":
        selected = GenerationTarget({}, "未知", None, error="模型未登记")
    elif kind == "unsupported":
        spec.mode = "video_extend"
    elif kind == "too_many_images":
        spec = VideoBrief(mode="reference_image_to_video", reference_asset_ids=[str(i) for i in range(31)])
    elif kind == "duplicate_roles":
        spec = VideoBrief(
            mode="reference_image_to_video", reference_asset_ids=["a", "a"]
        )
    else:
        selected = target(
            replace(
                profile, mode_constraints=(ModeConstraint("text_to_video", duration="fixed:-1"),)
            )
        )
    assert propose_settings(selected, spec, requested())["issues"]


def test_unknown_rule_and_impossible_combination_fail_closed():
    profile = get_profile("ark_seedance_v1", "doubao-seedance-2-5")
    for rule in (
        ParameterRule("unknown", allowed_values=(1,)),
        ParameterRule("duration_seconds", maximum=0),
    ):
        p = replace(profile, rules=(rule,))
        assert propose_settings(target(p), VideoBrief(mode="text_to_video"), requested())["issues"]


def test_seedance_accepts_thirty_references_and_adaptive_ratio():
    profile = get_profile("ark_seedance_v1", "doubao-seedance-2-5")
    spec = VideoBrief(mode="reference_image_to_video", reference_asset_ids=[str(i) for i in range(30)])
    result = propose_settings(target(profile), spec, requested(duration_seconds=7, aspect_ratio="adaptive"))
    assert not result["issues"]
    assert result["settings"]["duration_seconds"] == 7
    assert result["settings"]["aspect_ratio"] == "adaptive"
    validate_settings(target(profile), spec, result["settings"], result["wire"])


@pytest.mark.parametrize("complete", [True, False])
def test_custom_template_must_transport_reviewed_settings_and_materials(complete):
    profile = get_profile("generic_async_json_v1", "text_reference_media")
    selected = target(profile)
    body = {"duration": "{duration_seconds}", "ratio": "{aspect_ratio}", "first": "{first_frame_url}"}
    if complete:
        body.update(resolution="{resolution}", last="{last_frame_url}")
    selected.revision = SimpleNamespace(custom_template_json=json.dumps({"request_template_json": body}))
    spec = VideoBrief(mode="first_last_frame_to_video", first_frame_asset_id="first", last_frame_asset_id="last")
    result = propose_settings(selected, spec, requested())
    assert bool(result["issues"]) is (not complete)
    if not complete:
        assert "resolution" in result["issues"][0] and "last_frame_url" in result["issues"][0]
