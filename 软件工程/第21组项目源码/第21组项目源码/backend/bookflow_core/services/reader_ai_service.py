from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.ai.engine.openai_compatible_client import OpenAICompatibleClient
from bookflow_core.ai.engine.structured_output import call_json_schema, validate_structured_output
from bookflow_core.ai.kernel.agent import process_task
from bookflow_core.ai.kernel.intake import create_reader_request_task
from bookflow_core.ai.kernel.task_splitter import MAX_SPLIT_SUBTASKS
from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.models import AgentRun, ReaderAccount, SystemSetting, WorkTask
from bookflow_core.services.common import as_json
from bookflow_core.services.reader_portal_service import borrow_rules, reservation_rules


ALLOWED_KERNEL_TOOLS = {
    "ai_search_books",
    "ai_get_reader_activity",
    "ai_get_loans",
    "ai_get_reservations",
    "ai_get_hot_books",
    "ai_reader_create_borrow_request",
    "ai_reader_create_return_request",
    "ai_reader_create_reservation",
    "ai_reader_renew_borrow",
}

SAFE_TOOLS = sorted(ALLOWED_KERNEL_TOOLS)
LOAN_STATUSES = {"active", "borrowed", "renewable", "overdue", "returned"}
RESERVATION_STATUSES = {"active", "waiting", "ready", "ready_for_pickup", "fulfilled", "cancelled", "expired"}
BOOK_AVAILABILITY = {"available", "unavailable", "none"}
BOOK_SEARCH_SORTS = {"availability", "newest", "title"}


class ReaderAIToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class ReaderAIPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["direct_answer", "tool_call"]
    standalone_request: str = ""
    tool_calls: list[ReaderAIToolCall] = Field(default_factory=list)
    reply: str = ""
    llm_summary: str = Field(min_length=1)
    model_name: str = Field(min_length=1)


class ReaderAIReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1)


READER_AI_SYSTEM_PROMPT = """
You are BookFlow AI for library readers. The LLM is the reasoning core: understand the reader,
decide whether tools are needed, and compose the final answer naturally in Chinese.

Scope:
- You may help with public catalog search, book availability, book location, hot books,
  the current reader's own loans and reservations, borrowing/reservation rules,
  creating reservations, renewing eligible loans, and creating borrow/return service requests.
- Borrowing and returning physical books require staff confirmation. For these requests,
  create a borrow or return service request instead of claiming the book has been borrowed or returned.
- Reservations and renewals may be completed directly when tool results confirm success.
- You must not perform or suggest administrator operations, audits, risk handling, notifications,
  credit changes, AI rule changes, system settings, SQL, or actions on other readers.
- Never answer current catalog availability, locations, loans, or reservations from memory.
  Use the allowed tools when live data is needed.
- If a borrow, return, reservation, or renewal target is missing or ambiguous, ask a follow-up.
  Do not guess book ids, book codes, copy codes, loan ids, or reservation ids.
- If the reader asks outside this scope, politely refuse or redirect inside the reader scope.
- The backend will enforce reader identity. Do not ask for or use another reader's identity.
""".strip()


def reader_ai_suggestions(db: Session) -> list[str]:
    row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == "reader_ai_suggestions", SystemSetting.is_active == True))
    if not row or not row.setting_value:
        return []
    try:
        data = json.loads(row.setting_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def _require_llm_ready(client: OpenAICompatibleClient) -> None:
    try:
        client.require_ready()
    except BookFlowError as exc:
        raise BookFlowError("BookFlow AI 服务暂不可用。", code="READER_AI_UNAVAILABLE", details=exc.details) from exc


def _reader_context(db: Session, reader: ReaderAccount) -> dict[str, Any]:
    return {
        "reader": {
            "id": reader.id,
            "reader_code": reader.reader_code,
            "reader_type_code": reader.reader_type_code,
            "credit_score": reader.credit_score,
            "status": reader.status,
        },
        "borrow_rules": borrow_rules(db, reader),
        "reservation_rules": reservation_rules(db, reader),
    }


def _reader_tool_schemas(db: Session) -> list[dict[str, Any]]:
    return [item for item in tool_schemas_for_llm(db) if item.get("tool_name") in ALLOWED_KERNEL_TOOLS]


def _json_payload(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _history_messages(history: list[dict], *, limit: int = 8) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in history[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        messages.append({"role": role, "content": content[:1000]})
    return messages


def _plan_messages(db: Session, reader: ReaderAccount, *, text: str, history: list[dict]) -> list[dict[str, Any]]:
    schema_instruction = """
First rewrite the latest reader message into standalone_request, a self-contained request that can
be understood without reading chat history. Resolve pronouns, ellipsis, follow-up requests, and
references to previous results from the recent messages. If the request remains ambiguous, use
direct_answer and ask one specific clarifying question.

Return ONLY a JSON object with exactly these fields:
{
  "intent": "direct_answer" | "tool_call",
  "standalone_request": "<self-contained latest reader request>",
  "tool_calls": [{"tool_name": "<allowed tool name>", "arguments": {}, "reason": "<why this tool is needed>"}],
  "reply": "<Chinese reply only when intent is direct_answer>",
  "llm_summary": "<one-line summary>",
  "model_name": "<model name>"
}

Use direct_answer only for greetings, clarifying questions, rule explanations from provided context,
or out-of-scope refusals. Use tool_call for live catalog, availability, location, loans,
reservations, reader activity, hot-book queries, reservation creation, renewals,
borrow service requests, and return service requests. Do not add extra fields.
For catalog questions about titles, authors, ISBNs, genres, subjects, series, "do we have ...",
availability, copy counts, or shelf locations, use ai_search_books and pass the reader's natural
phrase as keyword; backend search will normalize fuzzy genre/series wording.
Tool arguments must be grounded in standalone_request plus recent messages; never pass vague
placeholders like "it", "that", "previous result", or an empty keyword when a concrete query can
be resolved from context.
If the reader challenges a previous catalog result, search again with a broader/raw phrase instead
of defending the earlier answer from memory.
""".strip()
    return [
        {"role": "system", "content": READER_AI_SYSTEM_PROMPT},
        {"role": "system", "content": schema_instruction},
        {"role": "system", "content": _json_payload({"available_tools": _reader_tool_schemas(db), "context": _reader_context(db, reader)})},
        *_history_messages(history),
        {"role": "user", "content": text},
    ]


def _plan_reader_chat(client, *, messages: list[dict[str, Any]], text: str) -> ReaderAIPlan:
    try:
        data = client.complete_json(messages=messages, temperature=0)
    except BookFlowError:
        raise
    except Exception as exc:
        raise BookFlowError(
            "BookFlow AI planner call failed.",
            code="AI_PLANNER_FAILED",
            details={"label": "reader_ai_plan", "reason": type(exc).__name__},
        ) from exc
    if "intent" not in data:
        intent = data.get("intent") or data.get("action") or data.get("plan_type") or ""
        if isinstance(intent, str):
            intent = intent.lower()
        data["intent"] = "tool_call" if intent in {"tool_call", "tool_calls", "tool"} else "direct_answer"
    if "reply" not in data:
        data["reply"] = data.get("reply") or data.get("message") or data.get("response") or data.get("content") or ""
    if "llm_summary" not in data:
        data["llm_summary"] = data.get("llm_summary") or data.get("summary") or "reader chat plan"
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
    return validate_structured_output(data, ReaderAIPlan, label="reader_ai_plan")


def _reply_messages(
    db: Session,
    reader: ReaderAccount,
    *,
    text: str,
    history: list[dict],
    plan: dict[str, Any],
    kernel_output: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": READER_AI_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "Compose the final reader-facing answer in natural Chinese. "
                "Use standalone_request from llm_plan to understand what the reader meant when it differs from the raw message. "
                "Use only the provided context and tool/kernel results as facts. "
                "When a service request, voucher code, reservation id/code, loan id, or renewal due date exists, mention it exactly. "
                "For ai_search_books results, mention normalized query/expansion when useful, separate total matches from returned items, "
                "and if metadata_only_match or notes are present, say the item matched catalog metadata such as category/keywords rather than claiming the genre is certainly correct. "
                "If results are empty or insufficient, say so and ask a useful follow-up. "
                "Return ONLY JSON: {\"reply\":\"...\"}."
            ),
        },
        {
            "role": "user",
            "content": _json_payload(
                {
                    "reader_message": text,
                    "history": history,
                    "reader_context": _reader_context(db, reader),
                    "llm_plan": plan,
                    "kernel_output": kernel_output,
                }
            ),
        },
    ]


def _as_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _sanitize_tool_call(call: ReaderAIToolCall, reader: ReaderAccount, *, fallback_query: str = "") -> dict[str, Any]:
    tool_name = call.tool_name.strip()
    if tool_name not in ALLOWED_KERNEL_TOOLS:
        raise BookFlowError(
            "Reader AI selected a tool outside reader permissions.",
            code="READER_AI_TOOL_FORBIDDEN",
            details={"tool_name": tool_name},
        )

    raw = call.arguments if isinstance(call.arguments, dict) else {}
    args: dict[str, Any]
    if tool_name == "ai_get_reader_activity":
        args = {"reader_code": reader.reader_code}
    elif tool_name == "ai_get_loans":
        args = {
            "reader_id": reader.id,
            "limit": _as_int(raw.get("limit"), default=20, minimum=1, maximum=50),
            "offset": _as_int(raw.get("offset"), default=0, minimum=0, maximum=500),
        }
        if raw.get("status") in LOAN_STATUSES:
            args["status"] = raw["status"]
        for key in ("book_id", "copy_id"):
            value = _positive_int(raw.get(key))
            if value is not None:
                args[key] = value
    elif tool_name == "ai_get_reservations":
        args = {
            "reader_id": reader.id,
            "limit": _as_int(raw.get("limit"), default=20, minimum=1, maximum=50),
            "offset": _as_int(raw.get("offset"), default=0, minimum=0, maximum=500),
        }
        if raw.get("status") in RESERVATION_STATUSES:
            args["status"] = raw["status"]
        for key in ("book_id", "copy_id"):
            value = _positive_int(raw.get(key))
            if value is not None:
                args[key] = value
    elif tool_name == "ai_search_books":
        args = {
            "keyword": str(raw.get("keyword") or fallback_query or "").strip()[:100],
            "limit": _as_int(raw.get("limit"), default=8, minimum=1, maximum=10),
        }
        if raw.get("availability") in BOOK_AVAILABILITY:
            args["availability"] = raw["availability"]
        if raw.get("sort") in BOOK_SEARCH_SORTS:
            args["sort"] = raw["sort"]
    elif tool_name == "ai_reader_create_borrow_request":
        args = {"reader_code": reader.reader_code}
        for key in ("book_id", "copy_id"):
            value = _positive_int(raw.get(key))
            if value is not None:
                args[key] = value
        if raw.get("book_code"):
            args["book_code"] = str(raw["book_code"]).strip()
    elif tool_name == "ai_reader_create_return_request":
        args = {"reader_code": reader.reader_code}
        loan_id = _positive_int(raw.get("loan_id"))
        if loan_id is not None:
            args["loan_id"] = loan_id
        if raw.get("copy_code"):
            args["copy_code"] = str(raw["copy_code"]).strip()
    elif tool_name == "ai_reader_create_reservation":
        args = {"reader_code": reader.reader_code}
        book_id = _positive_int(raw.get("book_id"))
        if book_id is not None:
            args["book_id"] = book_id
        if raw.get("book_code"):
            args["book_code"] = str(raw["book_code"]).strip()
    elif tool_name == "ai_reader_renew_borrow":
        args = {"reader_code": reader.reader_code}
        loan_id = _positive_int(raw.get("loan_id"))
        if loan_id is not None:
            args["loan_id"] = loan_id
    else:
        args = {"limit": _as_int(raw.get("limit"), default=6, minimum=1, maximum=10)}

    return {
        "tool_name": tool_name,
        "arguments": args,
        "reason": call.reason.strip() or "reader_ai_llm_plan",
        "stop_on_failure": True,
    }


def _sanitize_tool_calls(plan: ReaderAIPlan, reader: ReaderAccount) -> list[dict[str, Any]]:
    if plan.intent != "tool_call":
        return []
    calls = [_sanitize_tool_call(call, reader, fallback_query=plan.standalone_request) for call in plan.tool_calls[:MAX_SPLIT_SUBTASKS]]
    if not calls:
        raise BookFlowError("Reader AI plan contains no executable tool call.", code="AI_PLANNER_OUTPUT_INVALID")
    return calls


def _load_run_output(db: Session, run_id: int | None) -> dict[str, Any]:
    if not run_id:
        return {}
    run = db.get(AgentRun, run_id)
    if not run or not run.output_json:
        return {}
    try:
        data = json.loads(run.output_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _tool_result_data(record: dict[str, Any]) -> dict[str, Any]:
    result = _as_dict(record.get("result"))
    data = _as_dict(result.get("data"))
    return data


def _action_title(request_type: str, status: str) -> str:
    labels = {
        "borrow": "借书办理请求",
        "return": "还书办理请求",
        "reservation": "预约结果",
        "renew": "续借结果",
    }
    status_labels = {
        "pending": "待处理",
        "ready": "待馆员确认",
        "completed": "已完成",
        "cancelled": "已取消",
        "expired": "已过期",
        "failed": "失败",
        "waiting_human": "待人工介入",
    }
    base = labels.get(request_type, "办理结果")
    suffix = status_labels.get(status, status)
    return f"{base} · {suffix}" if suffix else base


def _service_request_action(row: dict[str, Any]) -> dict[str, Any]:
    request_type = str(row.get("request_type") or "")
    status = str(row.get("status") or "")
    result = _as_dict(row.get("result"))
    fields: list[dict[str, str]] = []
    for label, key in (
        ("请求码", "request_code"),
        ("凭证码", "voucher_code"),
        ("读者", "reader_code"),
        ("图书", "book_code"),
        ("副本", "copy_code"),
        ("借阅记录", "loan_code"),
        ("预约编号", "reservation_code"),
        ("到期时间", "expires_at"),
    ):
        value = row.get(key)
        if value not in (None, ""):
            fields.append({"label": label, "value": str(value)})
    for label, key in (
        ("新应还日期", "new_due_at"),
        ("应还日期", "due_at"),
        ("归还时间", "returned_at"),
        ("状态", "status"),
    ):
        value = result.get(key)
        if value not in (None, ""):
            fields.append({"label": label, "value": str(value)})
    return {
        "kind": "circulation_service_request",
        "request_type": request_type,
        "status": status,
        "title": _action_title(request_type, status),
        "summary": "请到服务台由馆员确认。" if request_type in {"borrow", "return"} and status == "ready" else "已同步到你的读者记录。",
        "fields": fields,
        "request": row,
    }


def _extract_reader_actions(kernel_output: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    service_requests: list[dict[str, Any]] = []
    for record in kernel_output.get("tool_results") or []:
        if not isinstance(record, dict):
            continue
        data = _tool_result_data(record)
        if not data:
            continue
        if data.get("request_code") and data.get("request_type"):
            service_requests.append(data)
            actions.append(_service_request_action(data))
    return actions, service_requests


def _process_reader_task(
    db: Session,
    reader: ReaderAccount,
    *,
    message: str,
    history: list[dict],
    plan: ReaderAIPlan,
    tool_calls: list[dict[str, Any]],
) -> tuple[WorkTask, dict[str, Any], dict[str, Any]]:
    task = create_reader_request_task(
        db,
        reader,
        message=message,
        history=history,
        answer=plan.reply,
        tool_calls=tool_calls,
        llm_plan=plan.model_dump(mode="json"),
        commit=False,
    )
    kernel_result = process_task(db, task.task_code, worker_id="reader-ai-kernel", commit=False)
    kernel_output = _load_run_output(db, kernel_result.get("run_id"))
    return task, kernel_result, kernel_output


def _store_final_answer(task: WorkTask, answer: str, *, actions: list[dict[str, Any]] | None = None, service_requests: list[dict[str, Any]] | None = None) -> None:
    try:
        payload = json.loads(task.source_payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["final_answer"] = answer
    if actions:
        payload["reader_actions"] = actions
    if service_requests:
        payload["service_requests"] = service_requests
    task.source_payload_json = as_json(payload)


def reader_ai_chat(db: Session, reader: ReaderAccount, *, message: str, history: list[dict] | None = None) -> dict:
    text = message.strip()
    if not text:
        raise BookFlowError("消息不能为空。", code="VALIDATION_ERROR")

    client = OpenAICompatibleClient(timeout_seconds=300)
    _require_llm_ready(client)
    chat_history = history or []
    try:
        plan = _plan_reader_chat(
            client,
            messages=_plan_messages(db, reader, text=text, history=chat_history),
            text=text,
        )
        tool_calls = _sanitize_tool_calls(plan, reader)
        task, kernel_result, kernel_output = _process_reader_task(
            db,
            reader,
            message=text,
            history=chat_history,
            plan=plan,
            tool_calls=tool_calls,
        )
        if tool_calls:
            reply = call_json_schema(
                client,
                messages=_reply_messages(
                    db,
                    reader,
                    text=text,
                    history=chat_history,
                    plan=plan.model_dump(mode="json"),
                    kernel_output=kernel_output,
                ),
                schema=ReaderAIReply,
                label="reader_ai_reply",
                temperature=0.2,
            ).reply.strip()
        else:
            reply = plan.reply.strip()
        if not reply:
            raise BookFlowError("Reader AI reply is missing.", code="AI_PLANNER_OUTPUT_INVALID")
        actions, service_requests = _extract_reader_actions(kernel_output)
        _store_final_answer(task, reply, actions=actions, service_requests=service_requests)
        db.commit()
        return {
            "answer": reply,
            "actions": actions,
            "service_requests": service_requests,
            "tool_scope": SAFE_TOOLS,
            "task_code": task.task_code,
            "kernel_run_id": kernel_result.get("run_code"),
            "llm_summary": plan.llm_summary,
        }
    except BookFlowError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise BookFlowError("BookFlow AI 服务暂不可用。", code="READER_AI_UNAVAILABLE") from exc
