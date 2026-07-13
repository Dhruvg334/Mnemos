from __future__ import annotations
import re
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, model_validator
T = TypeVar("T")
_BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def _check(value: Any, path: str = "value") -> None:
    if isinstance(value, str) and _BAD.search(value):
        raise ValueError(f"{path} contains disallowed control characters")
    if isinstance(value, (list, tuple)):
        for item in value: _check(item, path)
    if isinstance(value, dict):
        for key, item in value.items():
            _check(key, path); _check(item, path)

class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)
    @model_validator(mode="after")
    def safe_strings(self):
        for name in self.__class__.model_fields:
            _check(getattr(self, name, None), name)
        return self

class ORMModel(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)

class Meta(APIModel):
    request_id: str | None = None
    api_version: str = "v1"

class Envelope(APIModel, Generic[T]):
    data: T
    meta: Meta

class ErrorBody(APIModel):
    code: str
    message: str
    details: dict[str, Any] = {}
    retryable: bool = False
