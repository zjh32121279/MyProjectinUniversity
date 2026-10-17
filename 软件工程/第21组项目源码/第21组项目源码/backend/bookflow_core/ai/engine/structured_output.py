from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from bookflow_core.core.exceptions import BookFlowError

TModel = TypeVar("TModel", bound=BaseModel)


def validate_structured_output(data: dict, schema: type[TModel], *, label: str) -> TModel:
    if not isinstance(data, dict):
        raise BookFlowError(
            "BookFlow AI output must be a JSON object.",
            code="AI_PLANNER_OUTPUT_INVALID",
            details={"label": label, "reason": "json_object_required"},
        )
    try:
        return schema.model_validate(data)
    except PydanticValidationError as exc:
        raise BookFlowError(
            "BookFlow AI output does not match the required schema.",
            code="AI_PLANNER_OUTPUT_INVALID",
            details={"label": label, "errors": exc.errors()},
        ) from exc


def call_json_schema(client, *, messages: list[dict], schema: type[TModel], label: str, temperature: float = 0.1) -> TModel:
    try:
        data = client.complete_json(messages=messages, temperature=temperature)
    except BookFlowError:
        raise
    except Exception as exc:
        raise BookFlowError(
            "BookFlow AI planner call failed.",
            code="AI_PLANNER_FAILED",
            details={"label": label, "reason": type(exc).__name__},
        ) from exc
    return validate_structured_output(data, schema, label=label)
