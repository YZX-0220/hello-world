"""全片 AI 统筹规划（AI 导演向导）Schema。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DirectorOutlineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_duration: int = Field(..., ge=5, le=300, description="视频总时长（秒）")
    user_idea: str = Field(..., min_length=2, max_length=2000, description="用户核心创意描述")
    current_draft: str | None = Field(
        default=None, max_length=10000, description="当前剧本草稿（迭代修改时传入）"
    )
    revision_instruction: str | None = Field(
        default=None, max_length=2000, description="用户的修改方向指令"
    )

    @field_validator("user_idea")
    @classmethod
    def validate_user_idea(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("核心创意描述至少需要 2 个有效字符")
        return stripped

    @field_validator("current_draft", "revision_instruction")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DirectorOutlineResponse(BaseModel):
    script_draft: str
    recommended_segments: int


class DirectorBreakdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_duration: int = Field(..., ge=5, le=300, description="视频总时长（秒）")
    segment_count: int = Field(..., ge=1, le=20, description="拆解片段数量")
    script_draft: str = Field(..., min_length=10, max_length=15000, description="确认后的剧本正文")
    country_codes: list[str] = Field(
        default_factory=list, max_length=20, description="目标传播国家代码列表"
    )
    style_template_id: str | None = Field(
        default=None, max_length=64, description="提示词模板库中的风格ID或Code"
    )
    custom_style_desc: str | None = Field(
        default=None, max_length=2000, description="用户补充的自定义风格描述"
    )

    @field_validator("script_draft")
    @classmethod
    def validate_script_draft(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 10:
            raise ValueError("确认后的剧本正文至少需要 10 个有效字符")
        return stripped

    @field_validator("country_codes")
    @classmethod
    def normalize_country_codes(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(c.strip().upper() for c in value if c and c.strip()))

    @field_validator("style_template_id", "custom_style_desc")
    @classmethod
    def strip_optional_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SegmentNodeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=1, description="片段序号，从1开始")
    title: str = Field(..., description="节点命名，必须严格为：片段一、片段二...")
    duration: int = Field(default=15, ge=1, le=15, description="单片段时长（秒），范围 1-15 秒")
    timeline_prompt: str = Field(
        ...,
        min_length=1,
        description="按秒级切分的AI视频提示词，如：0-5秒... 5-10秒... 10-15秒...",
    )


class DirectorBreakdownResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_node_content: str = Field(
        ..., description="写入【整体风格设定】节点的完整提示词，包含画质、色调、光影、镜头语言基调"
    )
    cultural_node_content: str = Field(
        ...,
        description="写入【国际传播提示词】节点的内容，包含受众偏好指导与合并后的Negative Prompt",
    )
    image_asset_prompts: str = Field(
        ...,
        description="写入【图片素材提示词】节点的内容，列出需要通过AI生图提前生成的角色/场景首帧图提示词",
    )
    segments: list[SegmentNodeSchema] = Field(
        ..., description="按用户指定片段数拆解的分镜节点数组，长度必须等于 segment_count"
    )
