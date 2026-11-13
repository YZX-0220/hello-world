"""国家负面提示词仓储。"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import CULTURAL_GUIDANCE_CODE_EXISTS, CULTURAL_GUIDANCE_NOT_FOUND, AppError
from app.core.time import now
from app.db.models.cultural_guidance import CulturalGuidance

# 系统初始预置国家负面词与禁忌说明
DEFAULT_CULTURAL_GUIDANCES: tuple[dict, ...] = (
    {
        "code": "CN",
        "name": "中国",
        "negative_prompt": "刻板印象、陈旧年代感滤镜、失真东方符号、低质塑料感、生硬拼接",
        "taboo": "避免刻板印象与年代感错乱的陈旧滤镜",
        "sort_order": 1,
    },
    {
        "code": "US",
        "name": "美国",
        "negative_prompt": "过度说教、刻板印象、种族敏感符号、高高在上的宏大叙事灌输、虚假悬浮感",
        "taboo": "注意避免任何形式的刻板印象、种族敏感符号或过度主旋律视角的宏大叙事灌输",
        "sort_order": 2,
    },
    {
        "code": "GB",
        "name": "英国",
        "negative_prompt": "用力过猛的浮躁炫技、喧闹噪点、直白露骨的情绪宣泄、廉价工业CG感",
        "taboo": "避免用力过猛的浮躁炫技和过于直白露骨的情绪宣泄",
        "sort_order": 3,
    },
    {
        "code": "FR",
        "name": "法国",
        "negative_prompt": "工业化流水线塑料感、刺眼高频闪烁、生硬灌输式说理、过于喧闹紧绷的节奏",
        "taboo": "反感工业化流水线感过重或过于喧闹刺眼的塑料 CG 感；避免直接灌输式说理",
        "sort_order": 4,
    },
    {
        "code": "JP",
        "name": "日本",
        "negative_prompt": "夸张喧嚣的肢体冲突、生硬暴烈的情绪宣泄、历史争议图腾符号、刺目高饱和杂色",
        "taboo": "避免夸张喧嚣的肢体冲突与生硬的情绪宣泄；慎用容易引发历史语境争议的图腾符号",
        "sort_order": 5,
    },
    {
        "code": "DE",
        "name": "德国",
        "negative_prompt": "虚假浮夸、逻辑前后矛盾、透视畸变严重、空洞煽情、不严谨的工业结构",
        "taboo": "排斥虚假浮夸、逻辑前后矛盾或逻辑煽情的画面设计；注重规则与严谨度",
        "sort_order": 6,
    },
    {
        "code": "IN",
        "name": "印度",
        "negative_prompt": "阴暗沉闷压抑色调、冷淡死板运镜、宗教习俗冒犯元素、饮食文化禁忌元素",
        "taboo": "避免冷色调或沉闷压抑的灰暗构图；注意规避宗教习俗与特定饮食层面的文化冒犯",
        "sort_order": 7,
    },
)


class CulturalGuidanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_defaults(self) -> None:
        """检查并写入预置初始数据。"""
        existing = await self.session.exec(select(CulturalGuidance.id).limit(1))
        if existing.first() is not None:
            return
        for item in DEFAULT_CULTURAL_GUIDANCES:
            guidance = CulturalGuidance(
                code=item["code"],
                name=item["name"],
                negative_prompt=item["negative_prompt"],
                taboo=item["taboo"],
                sort_order=item["sort_order"],
                is_enabled=True,
                created_at=now(),
                updated_at=now(),
            )
            self.session.add(guidance)
        await self.session.commit()

    async def list_enabled(self) -> list[CulturalGuidance]:
        await self.ensure_defaults()
        stmt = (
            select(CulturalGuidance)
            .where(col(CulturalGuidance.is_enabled).is_(True))
            .order_by(col(CulturalGuidance.sort_order).asc(), col(CulturalGuidance.id).asc())
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_by_code(self, code: str) -> CulturalGuidance | None:
        norm_code = code.strip().upper()
        stmt = select(CulturalGuidance).where(col(CulturalGuidance.code) == norm_code)
        result = await self.session.exec(stmt)
        return result.first()

    async def list_by_codes(self, codes: list[str]) -> list[CulturalGuidance]:
        """按国家代码列表批量查询已启用的文化指引（空列表直接返回，避免空 IN 子句）。"""
        norm_codes = list(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))
        if not norm_codes:
            return []
        await self.ensure_defaults()
        stmt = (
            select(CulturalGuidance)
            .where(
                col(CulturalGuidance.code).in_(norm_codes),
                col(CulturalGuidance.is_enabled).is_(True),
            )
            .order_by(col(CulturalGuidance.sort_order).asc(), col(CulturalGuidance.id).asc())
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def create(
        self,
        code: str,
        name: str,
        negative_prompt: str,
        taboo: str | None = None,
        sort_order: int = 0,
        is_enabled: bool = True,
    ) -> CulturalGuidance:
        norm_code = code.strip().upper()
        existing = await self.get_by_code(norm_code)
        if existing:
            raise AppError(CULTURAL_GUIDANCE_CODE_EXISTS, f"国家代码 {norm_code} 已存在")

        guidance = CulturalGuidance(
            code=norm_code,
            name=name.strip(),
            negative_prompt=negative_prompt.strip(),
            taboo=taboo.strip() if taboo else None,
            sort_order=sort_order,
            is_enabled=is_enabled,
            created_at=now(),
            updated_at=now(),
        )
        self.session.add(guidance)
        await self.session.commit()
        await self.session.refresh(guidance)
        return guidance

    async def update_by_code(
        self,
        code: str,
        *,
        name: str | None = None,
        negative_prompt: str | None = None,
        taboo: str | None = None,
        sort_order: int | None = None,
        is_enabled: bool | None = None,
    ) -> CulturalGuidance:
        guidance = await self.get_by_code(code)
        if not guidance:
            raise AppError(CULTURAL_GUIDANCE_NOT_FOUND, f"国家代码 {code} 不存在")

        if name is not None:
            guidance.name = name.strip()
        if negative_prompt is not None:
            guidance.negative_prompt = negative_prompt.strip()
        if taboo is not None:
            guidance.taboo = taboo.strip() if taboo else None
        if sort_order is not None:
            guidance.sort_order = sort_order
        if is_enabled is not None:
            guidance.is_enabled = is_enabled

        guidance.updated_at = now()
        await self.session.commit()
        await self.session.refresh(guidance)
        return guidance
