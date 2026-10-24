"""认证接口的输入模型。所有输入拒绝未声明字段（extra=forbid）。"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import EmailCodePurpose


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailCodeRequest(_Strict):
    email: EmailStr
    purpose: EmailCodePurpose


class EmailCodeResponse(BaseModel):
    accepted: bool
    retry_after_seconds: int


class RegisterRequest(_Strict):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8, max_length=128)


class PasswordLoginRequest(_Strict):
    email: EmailStr
    password: str


class EmailCodeLoginRequest(_Strict):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(_Strict):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)
