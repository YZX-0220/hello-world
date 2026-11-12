"""提示词模板仓储（支持版本演进与一键回滚）。"""

import json
import re

from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import (
    PROMPT_TEMPLATE_FORBIDDEN,
    PROMPT_TEMPLATE_NOT_FOUND,
    PROMPT_TEMPLATE_VERSION_NOT_FOUND,
    AppError,
)
from app.core.ids import new_id
from app.core.time import now
from app.db.models.cultural_guidance import PromptTemplate, PromptTemplateVersion

# 平台预置模板
DEFAULT_PROMPT_TEMPLATES: tuple[dict, ...] = (
    {
        "code": "system_global_storyboard_v1",
        "name": "国际跨文化视频分镜标准模板",
        "category": "storyboard",
        "scope": "system",
        "description": "标准跨文化视频分镜脚本描述结构，适配国际传播叙事意图转译",
        "content": (
            "【分镜创作结构】\n"
            "- 画面主体：{{subject}}\n"
            "- 场景环境：{{scene}}\n"
            "- 镜头机位与运镜：{{camera}}\n"
            "- 动作时间线：{{motion}}\n"
            "- 光影氛围与色调：{{lighting}}\n"
            "- 核心受众与传播意图：{{audience}}\n"
            "- 视觉风格：{{visual_style}}"
        ),
        "negative_prompt": "画面撕裂、模型畸变、闪烁噪点、比例失真、工业塑料感、文字错乱",
    },
    {
        "code": "system_general_high_quality_negative_v1",
        "name": "全画质通用高质量负面提示词",
        "category": "negative",
        "scope": "system",
        "description": "适用于大多数视频/图片生成模型的通用排异负面提示词",
        "content": "过曝、欠曝、模糊、低分辨率、噪点粗糙、肢体畸变、多余手指、透视错乱、面部走形、静止死板、画面抖动撕裂",
        "negative_prompt": None,
    },
    {
        "code": "system_cinematic_realism_positive_v1",
        "name": "超写实电影质感正向模板",
        "category": "positive",
        "scope": "system",
        "description": "强调真人实景、自然光照、电影质感与呼吸感镜头语言",
        "content": (
            "8k 电影级分辨率，写实真人实景摄影，真实物理光学散景，"
            "电影感阿莱艾丽莎色彩风格，细腻皮肤纹理与环境质感，"
            "自然柔和的侧光与环境光漫射，镜头缓慢平稳推进，避免镜头漂移与浮夸特效。"
        ),
        "negative_prompt": "3D卡通、游戏CG感、劣质塑料感、蜡质皮肤、死白光线、浮夸特效",
    },
)


def extract_variables(text: str) -> list[str]:
    """提取 {{var}} 中的变量名并去重保序。"""
    if not text:
        return []
    vars_found = re.findall(r"\{\{\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*\}\}", text)
    seen = set()
    result = []
    for v in vars_found:
        v_clean = v.strip()
        if v_clean and v_clean not in seen:
            seen.add(v_clean)
            result.append(v_clean)
    return result


class PromptTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_defaults(self) -> None:
        """检查并初始化系统预置模板。"""
        existing = await self.session.exec(
            select(PromptTemplate.id).where(PromptTemplate.scope == "system").limit(1)
        )
        if existing.first() is not None:
            return

        for item in DEFAULT_PROMPT_TEMPLATES:
            vars_list = extract_variables(item["content"])
            template_id = new_id()
            now_dt = now()
            tpl = PromptTemplate(
                id=template_id,
                user_id=None,
                code=item["code"],
                scope="system",
                category=item["category"],
                name=item["name"],
                description=item["description"],
                content=item["content"],
                negative_prompt=item["negative_prompt"],
                variables_json=json.dumps(vars_list, ensure_ascii=False),
                current_version=1,
                status="active",
                created_at=now_dt,
                updated_at=now_dt,
            )
            version = PromptTemplateVersion(
                id=new_id(),
                template_id=template_id,
                version=1,
                name=item["name"],
                content=item["content"],
                negative_prompt=item["negative_prompt"],
                variables_json=json.dumps(vars_list, ensure_ascii=False),
                source_type="init",
                change_note="系统内置预置版本",
                created_by=None,
                created_at=now_dt,
            )
            self.session.add(tpl)
            self.session.add(version)
        await self.session.commit()

    async def list_templates(
        self,
        *,
        user_id: str | None = None,
        category: str | None = None,
        scope: str | None = None,
        q: str | None = None,
    ) -> list[PromptTemplate]:
        await self.ensure_defaults()
        stmt = select(PromptTemplate).where(PromptTemplate.status != "deleted")

        # 归属过滤：如果指定了 user_id，可见系统预置 + 属于该用户的模板；未指定且未登录时仅可见系统预置
        if scope == "system":
            stmt = stmt.where(PromptTemplate.scope == "system")
        elif scope == "user":
            if user_id:
                stmt = stmt.where(PromptTemplate.scope == "user", PromptTemplate.user_id == user_id)
            else:
                return []
        else:
            if user_id:
                stmt = stmt.where(
                    or_(
                        PromptTemplate.scope == "system",
                        PromptTemplate.user_id == user_id,
                    )
                )
            else:
                stmt = stmt.where(PromptTemplate.scope == "system")

        if category:
            stmt = stmt.where(PromptTemplate.category == category)
        if q:
            search = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    col(PromptTemplate.name).like(search),
                    col(PromptTemplate.content).like(search),
                    col(PromptTemplate.description).like(search),
                )
            )

        stmt = stmt.order_by(
            col(PromptTemplate.updated_at).desc(), col(PromptTemplate.created_at).desc()
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_by_id(self, template_id: str) -> PromptTemplate | None:
        stmt = select(PromptTemplate).where(
            PromptTemplate.id == template_id, PromptTemplate.status != "deleted"
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def create(
        self,
        *,
        name: str,
        content: str,
        category: str = "positive",
        negative_prompt: str | None = None,
        description: str | None = None,
        code: str | None = None,
        scope: str = "user",
        user_id: str | None = None,
        change_note: str | None = "创建初始版本",
    ) -> tuple[PromptTemplate, PromptTemplateVersion]:
        template_id = new_id()
        now_dt = now()
        vars_list = extract_variables(content)
        vars_json = json.dumps(vars_list, ensure_ascii=False)

        template = PromptTemplate(
            id=template_id,
            user_id=user_id,
            code=code,
            scope=scope,
            category=category,
            name=name.strip(),
            description=description.strip() if description else None,
            content=content.strip(),
            negative_prompt=negative_prompt.strip() if negative_prompt else None,
            variables_json=vars_json,
            current_version=1,
            status="active",
            created_at=now_dt,
            updated_at=now_dt,
        )
        version = PromptTemplateVersion(
            id=new_id(),
            template_id=template_id,
            version=1,
            name=name.strip(),
            content=content.strip(),
            negative_prompt=negative_prompt.strip() if negative_prompt else None,
            variables_json=vars_json,
            source_type="init",
            change_note=change_note,
            created_by=user_id,
            created_at=now_dt,
        )
        self.session.add(template)
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(template)
        await self.session.refresh(version)
        return template, version

    async def update(
        self,
        template_id: str,
        user_id: str,
        *,
        name: str | None = None,
        category: str | None = None,
        content: str | None = None,
        negative_prompt: str | None = None,
        description: str | None = None,
        change_note: str | None = None,
    ) -> tuple[PromptTemplate, PromptTemplateVersion | None]:
        template = await self.get_by_id(template_id)
        if not template:
            raise AppError(PROMPT_TEMPLATE_NOT_FOUND, "提示词模板不存在")

        # 系统模板允许查看，若非当前用户所属则拒绝修改
        if template.scope == "user" and template.user_id != user_id:
            raise AppError(PROMPT_TEMPLATE_FORBIDDEN, "无权修改他人的提示词模板")

        # 检查正文、负面词、名称是否实际变动
        has_content_changed = (
            (content is not None and content.strip() != template.content)
            or (
                negative_prompt is not None
                and negative_prompt.strip() != (template.negative_prompt or "")
            )
            or (name is not None and name.strip() != template.name)
        )

        if name is not None:
            template.name = name.strip()
        if category is not None:
            template.category = category
        if description is not None:
            template.description = description.strip() if description else None

        new_version_obj: PromptTemplateVersion | None = None
        now_dt = now()

        if has_content_changed:
            if content is not None:
                template.content = content.strip()
            if negative_prompt is not None:
                template.negative_prompt = negative_prompt.strip() if negative_prompt else None

            vars_list = extract_variables(template.content)
            template.variables_json = json.dumps(vars_list, ensure_ascii=False)
            template.current_version += 1

            new_version_obj = PromptTemplateVersion(
                id=new_id(),
                template_id=template.id,
                version=template.current_version,
                name=template.name,
                content=template.content,
                negative_prompt=template.negative_prompt,
                variables_json=template.variables_json,
                source_type="edit",
                change_note=change_note or f"更新至 v{template.current_version}",
                created_by=user_id,
                created_at=now_dt,
            )
            self.session.add(new_version_obj)

        template.updated_at = now_dt
        await self.session.commit()
        await self.session.refresh(template)
        if new_version_obj:
            await self.session.refresh(new_version_obj)
        return template, new_version_obj

    async def list_versions(self, template_id: str) -> list[PromptTemplateVersion]:
        template = await self.get_by_id(template_id)
        if not template:
            raise AppError(PROMPT_TEMPLATE_NOT_FOUND, "提示词模板不存在")
        stmt = (
            select(PromptTemplateVersion)
            .where(PromptTemplateVersion.template_id == template_id)
            .order_by(col(PromptTemplateVersion.version).desc())
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_version(self, template_id: str, version_num: int) -> PromptTemplateVersion | None:
        stmt = select(PromptTemplateVersion).where(
            PromptTemplateVersion.template_id == template_id,
            PromptTemplateVersion.version == version_num,
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def rollback(
        self,
        template_id: str,
        user_id: str,
        target_version_num: int,
        change_note: str | None = None,
    ) -> tuple[PromptTemplate, PromptTemplateVersion]:
        template = await self.get_by_id(template_id)
        if not template:
            raise AppError(PROMPT_TEMPLATE_NOT_FOUND, "提示词模板不存在")
        if template.scope == "user" and template.user_id != user_id:
            raise AppError(PROMPT_TEMPLATE_FORBIDDEN, "无权回滚他人的提示词模板")

        target_ver = await self.get_version(template_id, target_version_num)
        if not target_ver:
            raise AppError(
                PROMPT_TEMPLATE_VERSION_NOT_FOUND,
                f"目标版本 v{target_version_num} 不存在",
            )

        now_dt = now()
        template.name = target_ver.name
        template.content = target_ver.content
        template.negative_prompt = target_ver.negative_prompt
        template.variables_json = target_ver.variables_json
        template.current_version += 1
        template.updated_at = now_dt

        rollback_version = PromptTemplateVersion(
            id=new_id(),
            template_id=template.id,
            version=template.current_version,
            name=target_ver.name,
            content=target_ver.content,
            negative_prompt=target_ver.negative_prompt,
            variables_json=target_ver.variables_json,
            source_type="rollback",
            change_note=change_note or f"回滚至历史版本 v{target_version_num}",
            created_by=user_id,
            created_at=now_dt,
        )
        self.session.add(rollback_version)
        await self.session.commit()
        await self.session.refresh(template)
        await self.session.refresh(rollback_version)
        return template, rollback_version

    async def delete(self, template_id: str, user_id: str) -> None:
        template = await self.get_by_id(template_id)
        if not template:
            raise AppError(PROMPT_TEMPLATE_NOT_FOUND, "提示词模板不存在")
        if template.scope == "user" and template.user_id != user_id:
            raise AppError(PROMPT_TEMPLATE_FORBIDDEN, "无权删除他人的提示词模板")
        template.status = "deleted"
        template.updated_at = now()
        await self.session.commit()
