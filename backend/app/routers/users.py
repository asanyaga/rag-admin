from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_active_user
from app.models import User
from app.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get the currently authenticated user."""
    return UserResponse.model_validate(current_user)
