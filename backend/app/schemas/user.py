from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import AuthProvider


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    auth_provider: AuthProvider
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
