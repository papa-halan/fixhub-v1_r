from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic_core import PydanticCustomError


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


def strip_non_blank(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise PydanticCustomError(
            "blank_text",
            "{field_name} cannot be blank",
            {"field_name": field_name},
        )
    return cleaned
