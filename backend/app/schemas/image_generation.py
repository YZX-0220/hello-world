from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImageModel = Literal[
    "doubao-seedream-5.0-pro",
    "doubao-seedream-5.0-flash",
    "doubao-seedream-5-0-pro-260628",
    "doubao-seedream-5-0-flash-260915",
]
ImageRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]


class ImageConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=40)
    api_key: str = Field(min_length=8, max_length=1000)
    model: ImageModel = "doubao-seedream-5.0-pro"
    account_label: str = Field(default="", max_length=80)
    linked_video_api_config_id: str | None = Field(default=None, max_length=64)


class ImageConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    api_key: str | None = Field(default=None, min_length=8, max_length=1000)
    model: ImageModel | None = None
    account_label: str | None = Field(default=None, max_length=80)
    linked_video_api_config_id: str | None = Field(default=None, max_length=64)


class ImagePromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=4000)
    aspect_ratio: ImageRatio = "1:1"
    conversation_id: str
    api_config_id: str = Field(default="platform", min_length=1, max_length=64)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=4)
    parent_job_id: str | None = Field(default=None, max_length=64)
    watermark: bool = False


class ImageJobCreate(ImagePromptRequest):
    api_config_id: str = Field(default="platform", min_length=1, max_length=64)
    source_node_id: str | None = Field(default=None, max_length=128)
