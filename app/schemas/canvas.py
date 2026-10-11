"""Canvas structure and node-scoped collaboration input."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanvasNode(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=128)
    type: Literal["text", "image", "video"]
    title: str = Field(default="", max_length=200)
    x: float = 0
    y: float = 0
    content: str | None = Field(default=None, max_length=100000)
    url: str | None = None


class CanvasConnection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=128)
    from_: str = Field(alias="from")
    to: str


class CanvasDocument(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)

    nodes: list[CanvasNode] = Field(default_factory=list, max_length=500)
    connections: list[CanvasConnection] = Field(default_factory=list, max_length=2000)
    pan: dict[str, float] = Field(default_factory=lambda: {"x": 120.0, "y": 120.0})
    zoom: float = Field(default=1, ge=0.1, le=10)

    @model_validator(mode="after")
    def validate_ids(self) -> "CanvasDocument":
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("节点 ID 不能重复")
        connection_ids = {connection.id for connection in self.connections}
        if len(connection_ids) != len(self.connections):
            raise ValueError("连线 ID 不能重复")
        if any(
            connection.from_ not in ids or connection.to not in ids
            for connection in self.connections
        ):
            raise ValueError("连线必须引用现有节点")
        return self

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class CanvasCollaboration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_node_id: str = Field(min_length=1, max_length=128)
    reference_node_ids: list[str] = Field(default_factory=list, max_length=50)
    apply_mode: Literal["replace", "append"] = "replace"


class ConfirmCanvasPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_node_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    expected_canvas_version: int = Field(ge=0)


class CanvasGenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_seconds: int = Field(ge=1, le=15, strict=True)
    resolution: Literal["480p", "720p", "1080p"]


class PrepareCanvasVideoRequest(CanvasGenerationSettings):
    model_config = ConfigDict(extra="forbid")
    node_ids: list[str] = Field(min_length=1, max_length=50)
    expected_canvas_version: int = Field(ge=0)
