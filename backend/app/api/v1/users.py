"""当前用户接口。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.models.user import User
from app.schemas.user import UserView

router = APIRouter()


@router.get("/users/me", status_code=200)
async def get_me(user: User = Depends(get_current_user)) -> UserView:
    return UserView.model_validate(user)
