from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIChatToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    arguments: dict = Field(default_factory=dict)
    reason: str = ""


class AIChatPatrolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["daily", "overdue", "collection-health", "reservations", "s04"]
    reason: str = Field(min_length=1)


class AIChatPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["direct_answer", "tool_call", "kernel_patrol"]
    standalone_request: str = ""
    tool_calls: list[AIChatToolCall] = Field(default_factory=list)
    patrol: AIChatPatrolRequest | None = None
    reply: str = ""
    llm_summary: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
