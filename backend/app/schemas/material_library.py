"""素材库请求、详情与分页类型，供 OpenAPI 和前端对接使用。"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
]
AssetID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
LibraryStatus = Literal["draft", "published"]


class CreateLibraryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    description: Description
    model_name: ShortText
    video_asset_id: AssetID
    cover_asset_id: AssetID | None = None
    status: LibraryStatus = "draft"


class PatchLibraryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, strict=True)
    title: ShortText | None = None
    description: Description | None = None
    model_name: ShortText | None = None
    video_asset_id: AssetID | None = None
    cover_asset_id: AssetID | None = None
    status: LibraryStatus | None = None

    @model_validator(mode="after")
    def check_changes(self) -> "PatchLibraryItem":
        changes = self.model_fields_set - {"expected_version"}
        if not changes:
            raise ValueError("至少修改一个字段")
        for field in changes - {"cover_asset_id"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        return self


class LibraryFileView(BaseModel):
    asset_id: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_ms: int | None
    content_url: str


class LibraryItemView(BaseModel):
    id: str
    title: str
    description: str
    model_name: str
    status: LibraryStatus
    version: int
    video: LibraryFileView
    cover: LibraryFileView | None
    created_at: datetime
    updated_at: datetime


class LibraryPage(BaseModel):
    items: list[LibraryItemView]
    next_cursor: str | None
