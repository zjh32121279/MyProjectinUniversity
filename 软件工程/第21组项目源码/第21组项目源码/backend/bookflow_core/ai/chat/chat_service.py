from __future__ import annotations

from sqlalchemy.orm import Session

from bookflow_core.ai.chat.chat_schemas import AIChatPlan
from bookflow_core.ai.chat.conversation_memory import ensure_conversation, recent_messages, save_message_pair
from bookflow_core.ai.chat.query_rewriter import context_messages_for_llm
from bookflow_core.ai.chat.reference_resolver import build_reference_context
from bookflow_core.ai.engine.prompt_builder import build_chat_plan_messages
from bookflow_core.ai.engine.response_composer import compose_chat_reply
from bookflow_core.ai.engine.structured_output import validate_structured_output
from bookflow_core.ai.kernel.agent import process_task
from bookflow_core.ai.kernel.intake import create_kernel_task, process_patrol
from bookflow_core.ai.tools.dispatcher import dispatch_tool
from bookflow_core.ai.tools.registry import get_tool_definition
from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.services.common import write_audit
from bookflow_core.ai.engine.openai_compatible_client import OpenAICompatibleClient


def _client(llm_client=None):
    return llm_client or OpenAICompatibleClient()


def _require_llm_ready(client) -> None:
    if hasattr(client, "require_ready"):
        client.require_ready()


def _run_patrol(db: Session, *, scenario: str, actor_id: str, llm_client, commit: bool) -> dict:
    return process_patrol(db, scenario=scenario, actor_id=actor_id, commit=commit, llm_client=llm_client)


def _plan_chat(db: Session, client, *, conversation_id: str, text: str) -> AIChatPlan:
    reference = build_reference_context(db)
    messages = build_chat_plan_messages(
            recent_messages=context_messages_for_llm(recent_messages(db, conversation_id, limit=8)),
            current_text=text,
            tool_schemas=tool_schemas_for_llm(db),
            recent_kernel_runs=reference["recent_kernel_runs"],
    )
    data = client.complete_json(messages=messages, temperature=0)
    # Normalize model output to match AIChatPlan schema.
    # Different models use different field names — map them.
    if "intent" not in data:
        # map common alternative field names
        intent = data.get("intent") or data.get("action") or data.get("plan_type") or ""
        if isinstance(intent, str):
            intent = intent.lower()
        if intent in ("tool_call", "tool_calls", "tool"):
            data["intent"] = "tool_call"
        elif intent in ("kernel_patrol", "patrol"):
            data["intent"] = "kernel_patrol"
        else:
            data["intent"] = "direct_answer"
        if "reply" not in data:
            data["reply"] = data.get("reply") or data.get("message") or data.get("response") or data.get("content") or ""
        if "llm_summary" not in data:
            data["llm_summary"] = data.get("llm_summary") or data.get("summary") or "chat plan"
        if "model_name" not in data:
            data["model_name"] = data.get("model_name") or data.get("model") or "unknown"
        if "tool_calls" not in data:
            raw_calls = data.get("tool_calls") or data.get("tools") or data.get("calls") or []
            data["tool_calls"] = []
            for item in raw_calls if isinstance(raw_calls, list) else []:
                if isinstance(item, dict):
                    data["tool_calls"].append({"tool_name": item.get("tool_name", item.get("name", "")), "arguments": item.get("arguments", item.get("payload", item.get("args", {})))})
        if "patrol" not in data:
            data["patrol"] = data.get("patrol") or None
    if "reply" not in data:
        data["reply"] = data.get("reply") or data.get("message") or data.get("response") or data.get("content") or ""
    if "llm_summary" not in data:
        data["llm_summary"] = data.get("llm_summary") or data.get("summary") or "chat plan"
    if "model_name" not in data:
        data["model_name"] = data.get("model_name") or data.get("model") or "unknown"
    if "standalone_request" not in data:
        data["standalone_request"] = data.get("standalone_query") or data.get("resolved_request") or data.get("query") or text
    if "tool_calls" not in data:
        data["tool_calls"] = data.get("tools") or data.get("calls") or []
    if "tool_calls" in data and isinstance(data["tool_calls"], list):
        normalized_calls = []
        for item in data["tool_calls"]:
            if not isinstance(item, dict):
                continue
            normalized_calls.append(
                {
                    "tool_name": item.get("tool_name", item.get("name", "")),
                    "arguments": item.get("arguments", item.get("payload", item.get("args", {}))),
                    "reason": item.get("reason", ""),
                }
            )
        data["tool_calls"] = normalized_calls
    return validate_structured_output(data, AIChatPlan, label="chat_plan")


def _arguments_with_standalone_request(db: Session, tool_name: str, arguments: dict, standalone_request: str) -> dict:
    payload = dict(arguments or {})
    if not standalone_request.strip():
        return payload
    try:
        schema = get_tool_definition(db, tool_name).input_schema
    except Exception:
        return payload
    properties = schema.get("properties") if isinstance(schema, dict) else {}
    keyword_schema = properties.get("keyword") if isinstance(properties, dict) else None
    if isinstance(keyword_schema, dict) and keyword_schema.get("type") == "string" and not str(payload.get("keyword") or "").strip():
        payload["keyword"] = standalone_request.strip()
    return payload


def chat(
    db: Session,
    *,
    conversation_id: str,
    text: str,
    actor_id: str = "admin",
    commit: bool = True,
    llm_client=None,
) -> dict:
    client = _client(llm_client)
    _require_llm_ready(client)
    ensure_conversation(db, conversation_id, actor_id)
    plan = _plan_chat(db, client, conversation_id=conversation_id, text=text)
    plan_payload = plan.model_dump(mode="json")
    standalone_request = plan.standalone_request.strip() or text
    tool_results: list[dict] = []
    patrol_result: dict | None = None
    try:
        if plan.intent == "tool_call":
            if len(plan.tool_calls) > 1:
                calls = [
                    {
                        "tool_name": call.tool_name,
                        "arguments": _arguments_with_standalone_request(db, call.tool_name, call.arguments, standalone_request),
                        "reason": call.reason or "admin_ai_multi_intent",
                    }
                    for call in plan.tool_calls
                ]
                task = create_kernel_task(
                    db,
                    title="Admin AI multi-intent request",
                    description=standalone_request[:500],
                    priority="normal",
                    source_type="ai_admin",
                    task_group="review",
                    source_payload={
                        "kernel_intent": "admin_ai_chat",
                        "admin_message": text,
                        "standalone_request": standalone_request,
                        "tool_calls": calls,
                        "llm_plan": plan_payload,
                        "process_subtasks_immediately": True,
                    },
                    execution_context={"entrypoint": "admin_ai_chat", "conversation_id": conversation_id},
                    actor_type="admin",
                    actor_id=actor_id,
                    commit=False,
                )
                patrol_result = process_task(db, task.task_code, worker_id=actor_id, commit=False)
                patrol_result["task_code"] = task.task_code
            else:
                for call in plan.tool_calls:
                    arguments = _arguments_with_standalone_request(db, call.tool_name, call.arguments, standalone_request)
                    result = dispatch_tool(db, call.tool_name, arguments, actor_id=actor_id, planner_context=True, autonomous=False)
                    tool_results.append({"tool_name": call.tool_name, "arguments": arguments, "reason": call.reason, "result": result})
                    if result["status"] in {"waiting_authorization", "needs_clarification"}:
                        break
        elif plan.intent == "kernel_patrol":
            if plan.patrol is None:
                raise BookFlowError("AI chat patrol plan missing scenario.", code="AI_PLANNER_OUTPUT_INVALID")
            patrol_result = _run_patrol(db, scenario=plan.patrol.scenario, actor_id=actor_id, llm_client=client, commit=False)
        reply = compose_chat_reply(
            client,
            current_text=text,
            plan=plan_payload,
            tool_results=tool_results,
            kernel_result=patrol_result,
        ) if (tool_results or patrol_result) else plan.reply.strip()
        if not reply:
            raise BookFlowError("AI chat reply is missing.", code="AI_PLANNER_OUTPUT_INVALID")
        save_message_pair(db, conversation_id=conversation_id, user_text=text, assistant_text=reply)
        write_audit(
            db,
            actor_type="ai_admin",
            actor_id=actor_id,
            action="ai_chat",
            target_table="ai_conversations",
            target_id=conversation_id,
            detail={
                "llm_summary": plan.llm_summary,
                "standalone_request": standalone_request,
                "tool_results": tool_results,
                "kernel_run_id": patrol_result.get("run_code") if patrol_result else None,
            },
        )
        if commit:
            db.commit()
        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "tool_calls": [{"tool_name": item["tool_name"], "payload": item["arguments"], "arguments": item["arguments"]} for item in tool_results],
            "tool_results": tool_results,
            "kernel_run_id": patrol_result.get("run_code") if patrol_result else None,
            "llm_summary": plan.llm_summary,
            "llm_generated": True,
        }
    except Exception:
        if commit:
            db.rollback()
        raise
