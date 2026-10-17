from __future__ import annotations

from pydantic import BaseModel


class SearchEventRequest(BaseModel):
    keyword: str
