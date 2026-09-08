"""文本 Agent 相关的 Pydantic 领域模型：结构化视频方案（VideoBrief）与 Agent 输出。

对应《实施计划》6.1 / 4.4 节。既有用于 AI 输出的完整定义，也有 PATCH 用的部分定义。
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import VideoMode


class VideoBrief(BaseModel):
    """结构化视频方案（完整定义）。字段多为可选，允许方案逐步补全。"""

    objective: str | None = None  # 视频目标
    audience: str | None = None  # 目标受众
    language: str | None = None  # 内容语言，如 zh-CN
    duration_seconds: int | None = Field(default=None, ge=1, le=120)
    aspect_ratio: str | None = None  # 16:9 / 9:16 / 1:1
    mode: VideoMode | None = None  # 生成模式
    visual_style: str | None = None  # 视觉风格
    subject: str | None = None  # 主要主体
    scene: str | None = None  # 场景描述
    camera: str | None = None  # 镜头设计
    motion: str | None = None  # 动作设计
    lighting: str | None = None  # 光线设计
    narration: str | None = None  # 旁白
    negative_prompt: str | None = None  # 负面提示
    first_frame_asset_id: str | None = None
    last_frame_asset_id: str | None = None
    reference_asset_ids: list[str] = Field(default_factory=list)
    source_video_asset_id: str | None = None
    audio_asset_id: str | None = None


class VideoBriefPatch(BaseModel):
    """视频方案的部分更新（PATCH）。缺失表示不修改；显式 null/[] 表示清空对应字段。"""

    model_config = ConfigDict(extra="forbid")

    objective: str | None = None
    audience: str | None = None
    language: str | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=120)
    aspect_ratio: str | None = None
    mode: VideoMode | None = None
    visual_style: str | None = None
    subject: str | None = None
    scene: str | None = None
    camera: str | None = None
    motion: str | None = None
    lighting: str | None = None
    narration: str | None = None
    negative_prompt: str | None = None
    first_frame_asset_id: str | None = None
    last_frame_asset_id: str | None = None
    reference_asset_ids: list[str] | None = None
    source_video_asset_id: str | None = None
    audio_asset_id: str | None = None


class AgentOutput(BaseModel):
    """Agent 的输出：用户可见回复 + 本轮结构方案修改 + 辅助信息。

    字段缺失表示"不修改"；显式 null 只允许清空白名单字段；空列表表示明确清空。
    """

    model_config = ConfigDict(extra="ignore")

    reply: str = ""
    state_patch: VideoBriefPatch = Field(default_factory=VideoBriefPatch)
    missing_fields: list[str] = Field(default_factory=list)
    ready_for_generation: bool = False
    suggested_prompt: str | None = None
    search_requests: list[str] = Field(default_factory=list)  # 需要联网时填查询词（仅联网开启时支持）
