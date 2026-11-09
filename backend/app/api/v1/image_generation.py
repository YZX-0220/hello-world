from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.db.models.user import User
from app.schemas.image_generation import (
    ImageConfigCreate,
    ImageConfigPatch,
    ImageJobCreate,
    ImagePromptRequest,
)
from app.services.image_generation_service import ImageGenerationService, job_view, options

router = APIRouter(tags=["生图"])


@router.post("/image-reference-uploads", status_code=201, dependencies=[Depends(require_csrf)])
async def upload_reference(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    from app.services.image_inputs import max_reference_bytes

    data = await file.read(max_reference_bytes() + 1)
    return await ImageGenerationService(session).upload_reference(
        user.id, conversation_id, data, file.filename or "reference.png"
    )


@router.get("/image-generation/options")
async def image_options(user: User = Depends(get_current_user)):
    return options()


@router.get("/image-api-configs")
async def list_configs(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(db_session)
):
    return await ImageGenerationService(session).configs(user.id)


@router.post("/image-api-configs", status_code=201, dependencies=[Depends(require_csrf)])
async def create_config(
    req: ImageConfigCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await ImageGenerationService(session).create_config(user.id, req)


@router.patch("/image-api-configs/{config_id}", dependencies=[Depends(require_csrf)])
async def patch_config(
    config_id: str,
    req: ImageConfigPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await ImageGenerationService(session).patch_config(user.id, config_id, req)


@router.delete(
    "/image-api-configs/{config_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_config(
    config_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    await ImageGenerationService(session).delete_config(user.id, config_id)
    return Response(status_code=204)


@router.post("/image-prompt-suggestions", dependencies=[Depends(require_csrf)])
async def suggest_prompt(
    req: ImagePromptRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await ImageGenerationService(session).suggest(user.id, req)


@router.post("/image-jobs", status_code=201, dependencies=[Depends(require_csrf)])
async def create_job(
    req: ImageJobCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
):
    return await ImageGenerationService(session).create(user.id, req, idempotency_key)


@router.get("/image-jobs")
async def list_jobs(
    conversation_id: str = Query(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await ImageGenerationService(session).list(user.id, conversation_id)


@router.get("/image-jobs/{job_id}")
async def get_job(
    job_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(db_session)
):
    return job_view(await ImageGenerationService(session).get(user.id, job_id))


@router.post("/image-jobs/{job_id}/retry-storage", dependencies=[Depends(require_csrf)])
async def retry_storage(
    job_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(db_session)
):
    return await ImageGenerationService(session).retry_storage(user.id, job_id)


@router.post("/image-jobs/{job_id}/cancel", dependencies=[Depends(require_csrf)])
async def cancel_job(
    job_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(db_session)
):
    return await ImageGenerationService(session).cancel(user.id, job_id)


@router.post("/image-jobs/{job_id}/acknowledge-unknown", dependencies=[Depends(require_csrf)])
async def acknowledge_unknown(
    job_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(db_session)
):
    return await ImageGenerationService(session).acknowledge_unknown(user.id, job_id)
