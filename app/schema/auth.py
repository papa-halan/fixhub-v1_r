from __future__ import annotations

from pydantic import ValidationInfo, field_validator

from app.schema.base import SchemaModel, strip_non_blank


class LoginRequest(SchemaModel):
    email: str
    password: str
    next_path: str = "/"

    @field_validator("email", "password")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return strip_non_blank(value, info.field_name)


class LoginResponse(SchemaModel):
    redirect_path: str
