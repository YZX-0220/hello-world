"""Portrait notes derive from current visual observations and remain outside creative prompts."""

import json

import pytest
from app.db.models.project import VideoProjectVersion
from app.providers.text.base import TextResult
from app.schemas.agent import AgentOutput, VideoBrief
from app.services.agent_service import AgentService
from app.services.video_review import PORTRAIT_REFERENCE_NOTICE, REVIEW_CLOSING, review_markdown
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from test_canvas import create_project, preparation
from test_canvas_vision import PATCH, add_image, save, urls
from test_canvas_vision import isolated_network as isolated_network
from test_canvas_vision import providers as providers


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", False),
        ("false", False),
        (1, False),
        (0, False),
        (None, False),
        ([], False),
    ],
)
def test_parser_accepts_only_actual_json_boolean_true(value, expected):
    agent = object.__new__(AgentService)
    output = agent._parse_output({"state_patch": PATCH, "contains_portrait": value}, "")
    assert output.contains_portrait is expected
    assert "contains_portrait" not in output.state_patch.model_dump()


def test_old_output_schema_and_direct_patch_remain_compatible():
    agent = object.__new__(AgentService)
    assert agent._parse_output({"state_patch": PATCH}, "").contains_portrait is False
    assert agent._parse_output(None, "人物肖像").contains_portrait is False
    direct = agent._parse_output({"subject": "人物", "contains_portrait": True}, "")
    assert direct.contains_portrait is True
    assert direct.state_patch.subject == "人物"


@pytest.mark.parametrize("invalid", ["true", "false", 1, None])
def test_output_field_is_strict_boolean(invalid):
    with pytest.raises(ValidationError):
        AgentOutput(contains_portrait=invalid)


@pytest.mark.parametrize("blocked", [True, False])
def test_portrait_notice_is_exactly_last_even_when_review_is_blocked(blocked):
    spec = VideoBrief(duration_seconds=5, aspect_ratio="16:9", **PATCH)
    output = AgentOutput(contains_portrait=True)
    content = review_markdown(spec, output, "720p", issues=["需要补齐场景"] if blocked else [])
    assert content.endswith(PORTRAIT_REFERENCE_NOTICE)
    assert content.count(PORTRAIT_REFERENCE_NOTICE) == 1
    if not blocked:
        assert content.index(REVIEW_CLOSING) < content.index(PORTRAIT_REFERENCE_NOTICE)
    ordinary = review_markdown(spec, AgentOutput(), "720p")
    assert PORTRAIT_REFERENCE_NOTICE not in ordinary


async def record_for(db_engine, project):
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        row = (
            await session.exec(
                select(VideoProjectVersion).where(
                    VideoProjectVersion.project_id == project["id"],
                    VideoProjectVersion.version == project["current_spec_version"],
                )
            )
        ).one()
    return json.loads(row.generation_review_json)


async def review(client, headers, cid, project):
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        headers=headers,
        json=preparation(["target"], project["canvas_version"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("detected", [True, False, "true", None])
async def test_visual_portrait_flag_controls_tail_notice_and_persists_without_polluting_prompt(
    client, db_engine, providers, detected
):
    visual, _text = providers
    payload = {"state_patch": PATCH}
    if detected is not None:
        payload["contains_portrait"] = detected
    visual.generate.return_value = TextResult(structured=payload)
    cid, headers, document = await create_project(client)
    # Deliberately portrait-like text/title: neither may substitute for the model's image flag.
    document["nodes"][0]["content"] = "人物肖像视频"
    await add_image(client, cid, headers, document, ident="portrait-face-photo", linked=True)
    project = await save(client, cid, headers, document)
    result = await review(client, headers, cid, project)
    expected = detected is True
    rendered = result["canvas_data"]["generation_review"]
    assert rendered["contains_portrait"] is expected
    assert rendered["status"] == "ready"
    assert rendered["content"].endswith(PORTRAIT_REFERENCE_NOTICE) is expected
    stored = await record_for(db_engine, result)
    assert stored["contains_portrait"] is expected
    assert "contains_portrait" not in result["current_spec"]
    assert PORTRAIT_REFERENCE_NOTICE not in stored["compiled_prompt"]
    assert "订阅通道" not in stored["compiled_prompt"]
    assert urls(visual.generate.call_args.args[0])
    instructions = json.dumps(visual.generate.call_args.args[0], ensure_ascii=False)
    assert "contains_portrait" in instructions and "不得根据正文" in instructions
    loaded = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert loaded["canvas_data"]["generation_review"] == rendered
    # Saving arbitrary canvas metadata must restore the server-authored flag and content.
    changed = loaded["canvas_data"]
    changed["generation_review"]["contains_portrait"] = not expected
    changed["generation_review"]["content"] = "伪造提醒"
    restored = await save(client, cid, headers, changed, loaded["canvas_version"])
    assert restored["canvas_data"]["generation_review"] == rendered


async def test_no_image_cannot_activate_portrait_notice_even_if_model_says_true(
    client, db_engine, providers
):
    visual, text = providers
    text.generate.side_effect = None
    text.generate.return_value = TextResult(
        structured={"state_patch": PATCH, "contains_portrait": True}
    )
    cid, headers, document = await create_project(client)
    document["nodes"][0]["content"] = "真实人物肖像，特写人脸"
    project = await save(client, cid, headers, document)
    result = await review(client, headers, cid, project)
    assert result["canvas_data"]["generation_review"]["contains_portrait"] is False
    assert PORTRAIT_REFERENCE_NOTICE not in result["canvas_data"]["generation_review"]["content"]
    assert (await record_for(db_engine, result))["contains_portrait"] is False
    visual.generate.assert_not_awaited()


@pytest.mark.parametrize(
    "first_detected,second_detected,blocked",
    [(True, False, False), (False, True, False), (True, False, True)],
)
async def test_portrait_detection_is_ored_across_review_repair_rounds(
    client, db_engine, providers, first_detected, second_detected, blocked
):
    visual, _text = providers
    visual.generate.side_effect = [
        TextResult(
            structured={"state_patch": {"subject": "人物"}, "contains_portrait": first_detected}
        ),
        TextResult(
            structured={
                "state_patch": {} if blocked else PATCH,
                "contains_portrait": second_detected,
            }
        ),
    ]
    cid, headers, document = await create_project(client)
    await add_image(client, cid, headers, document, linked=True)
    project = await save(client, cid, headers, document)
    result = await review(client, headers, cid, project)
    rendered = result["canvas_data"]["generation_review"]
    assert rendered["status"] == ("blocked" if blocked else "ready")
    assert rendered["contains_portrait"] is True
    assert rendered["content"].endswith(PORTRAIT_REFERENCE_NOTICE)
    assert visual.generate.await_count == 2
    assert all(urls(call.args[0]) for call in visual.generate.call_args_list)
    assert (await record_for(db_engine, result))["contains_portrait"] is True


async def test_legacy_review_record_without_portrait_field_restores_as_false(
    client, db_engine, providers
):
    from app.services.video_generation_policy import digest

    _visual, text = providers
    text.generate.side_effect = None
    text.generate.return_value = TextResult(structured={"state_patch": PATCH})
    cid, headers, document = await create_project(client)
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    result = await review(client, headers, cid, project)
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        row = (
            await session.exec(
                select(VideoProjectVersion).where(
                    VideoProjectVersion.project_id == result["id"],
                    VideoProjectVersion.version == result["current_spec_version"],
                )
            )
        ).one()
        record = json.loads(row.generation_review_json)
        record.pop("contains_portrait")
        record.pop("fingerprint")
        record["fingerprint"] = digest(record)
        row.generation_review_json = json.dumps(record, ensure_ascii=False)
        session.add(row)
        await session.commit()
    document = result["canvas_data"]
    document["generation_review"]["contains_portrait"] = True
    restored = await save(client, cid, headers, document, result["canvas_version"])
    rendered = restored["canvas_data"]["generation_review"]
    assert rendered["contains_portrait"] is False
    assert rendered["fingerprint"] == record["fingerprint"]
    assert PORTRAIT_REFERENCE_NOTICE not in rendered["content"]
