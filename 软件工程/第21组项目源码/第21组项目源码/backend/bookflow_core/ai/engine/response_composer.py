from __future__ import annotations

from pydantic import BaseModel, Field

from bookflow_core.ai.engine.prompt_builder import build_chat_reply_messages
from bookflow_core.ai.engine.structured_output import call_json_schema


class AIReply(BaseModel):
    reply: str = Field(min_length=1)


def compose_chat_reply(client, *, current_text: str, plan: dict, tool_results: list[dict], kernel_result: dict | None) -> str:
    data = call_json_schema(
        client,
        messages=build_chat_reply_messages(
            current_text=current_text,
            plan=plan,
            tool_results=tool_results,
            kernel_result=kernel_result,
        ),
        schema=AIReply,
        label="chat_reply",
        temperature=0,
    )
    return data.reply.strip()
