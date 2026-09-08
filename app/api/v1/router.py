"""v1 路由聚合。各模块路由在此 include，统一挂到 /api/v1 前缀。"""

from fastapi import APIRouter, FastAPI

from app.api.v1 import (
    assets,
    auth,
    conversations,
    provider_assets,
    users,
    video_api_configs,
    video_jobs,
    video_protocols,
)


def register_v1_routes(app: FastAPI) -> None:
    """把 v1 各模块路由挂到 /api/v1 前缀下。"""
    api_router = APIRouter()
    api_router.include_router(auth.router)
    api_router.include_router(users.router)
    api_router.include_router(conversations.router)
    api_router.include_router(video_protocols.router)
    api_router.include_router(video_api_configs.router)
    api_router.include_router(assets.router)
    api_router.include_router(provider_assets.router)
    api_router.include_router(video_jobs.router)
    app.include_router(api_router, prefix="/api/v1")
