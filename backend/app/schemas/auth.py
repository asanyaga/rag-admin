from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.user import UserResponse


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str
    full_name: str | None = None

    @field_validator('password_confirm')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(TokenResponse):
    user: UserResponse
