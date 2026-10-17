from __future__ import annotations

from pydantic import BaseModel, Field


class ReaderAIChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
