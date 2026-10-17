from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.ai.kernel.task_queue import (
    handle_task_failure,
    interrupt_task,
    lease_next_task,
    refresh_queue,
    write_checkpoint,
)
from bookflow_core.ai.kernel.followup import build_followup_steps
from bookflow_core.ai.kernel.ledger import (
    completed_execution,
    default_idempotency_key,
    ledger_to_skipped_result,
    record_execution_attempt,
)
from bookflow_core.ai.kernel.outcome import evaluate_execution_outcome
from bookflow_core.ai.kernel.sop import build_sop_plan
from bookflow_core.ai.kernel.task_splitter import MAX_SPLIT_SUBTASKS, create_task_package_children, extract_tool_steps, should_split_task
from bookflow_core.ai.tools.dispatcher import dispatch_tool
from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
from bookflow_core.ai.engine.openai_compatible_client import OpenAICompatibleClient
from bookflow_core.ai.engine.structured_output import call_json_schema
from bookflow_core.core.exceptions import BusinessRuleError
from bookflow_core.core.time import now
from bookflow_core.models import AgentRun, AgentStep, WorkTask
from bookflow_core.services.common import as_json, write_audit
from bookflow_core.services.task_service import (
    TASK_STATUS_AI_PROCESSING,
    TASK_STATUS_PENDING,
    ai_complete_task,
    ai_start_task,
    get_task,
    record_task_event,
    task_to_dict,
)

MAX_DYNAMIC_ITERATIONS = 8


class KernelPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    stop_on_failure: bool = True


class KernelTaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["execute_tool", "execute_plan", "handoff", "complete"]
    tool_name: str = ""
    arguments: dict = Field(default_factory=dict)
    steps: list[KernelPlanStep] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


def _run_code(prefix: str = "KERNEL") -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _json_dict(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def _run_output(db: Session, run_id: int | None) -> dict:
    if not run_id:
        return {}
    run = db.get(AgentRun, run_id)
    if not run or not run.output_json:
        return {}
    return _json_dict(run.output_json)


def _write_step(db: Session, run: AgentRun, name: str, status: str, detail: dict) -> None:
    stamp = now()
    db.add(
        AgentStep(
            run_id=run.id,
            step_name=name,
            status=status,
            detail_json=as_json(detail),
            started_at=stamp,
            finished_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
    )


def _aware(value):
    from bookflow_core.core.time import CST
    return value if value.tzinfo is not None else value.replace(tzinfo=CST)


def _is_active_foreign_lease(task: WorkTask, worker_id: str) -> bool:
    if not task.lease_owner or task.lease_owner == worker_id:
        return False
    if not task.lease_expires_at:
        return False
    return _aware(task.lease_expires_at) > now()


def _ensure_claimed(db: Session, task: WorkTask, *, worker_id: str, run_id: int, lease_seconds: int) -> WorkTask:
    if task.status == TASK_STATUS_PENDING:
        task.lease_owner = worker_id
        task.lease_expires_at = now() + timedelta(seconds=max(30, int(lease_seconds)))
        task.attempt_count = int(task.attempt_count or 0) + 1
        return ai_start_task(db, task.task_code, run_id=run_id, actor_id=worker_id, commit=False)
    if task.status == TASK_STATUS_AI_PROCESSING:
        if _is_active_foreign_lease(task, worker_id):
            raise BusinessRuleError(
                "Task is leased by another AI worker.",
                details={"task_code": task.task_code, "lease_owner": task.lease_owner, "worker_id": worker_id},
            )
        task.lease_owner = worker_id
        task.lease_expires_at = now() + timedelta(seconds=max(30, int(lease_seconds)))
        task.ai_run_id = run_id
        return task
    raise BusinessRuleError("AI Kernel cannot process task from current status.", details={"status": task.status})


def _client(llm_client=None):
    return llm_client or OpenAICompatibleClient(timeout_seconds=300)


def _engine_ready(client) -> bool:
    if not hasattr(client, "status"):
        return True
    try:
        return bool(client.status().enabled)
    except Exception:
        return False


def _planner_messages(db: Session, task: WorkTask, payload: dict) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are the BookFlow AI Kernel planner. Decide the next step for exactly one work task. "
                "Return only JSON matching KernelTaskPlan. Use execute_tool only when one registered tool "
                "can safely handle the next task step with complete arguments. Use execute_plan for a short "
                "registered-tool sequence only when the steps are already concrete; each step must have complete arguments and a reason. "
                "Use handoff if data is missing, the task needs human judgement, or the operation is outside "
                "available tools. If dynamic_observations exist, use them to decide the next step instead of repeating work. "
                "Use complete when the observations show the task is done."
            ),
        },
        {"role": "system", "content": as_json({"available_tools": tool_schemas_for_llm(db)})},
        {"role": "user", "content": as_json({"task": task_to_dict(task), "source_payload": payload})},
    ]


def _fallback_plan(task: WorkTask, payload: dict) -> dict:
    if bool(task.requires_human_confirmation):
        return {
            "action": "handoff",
            "reason": "human_confirmation_required",
            "payload": payload,
        }
    if task.task_group in {"borrow", "reservation", "catalog", "shelving", "risk"}:
        return {
            "action": "handoff",
            "reason": "missing_executable_tool_context",
            "payload": payload,
        }
    return {
        "action": "complete",
        "reason": "low_risk_administrative_task",
        "payload": payload,
    }


def _extract_plan_steps(payload: dict) -> list[dict]:
    return extract_tool_steps(payload, limit=MAX_SPLIT_SUBTASKS)


def _plan_task(db: Session, task: WorkTask, *, llm_client=None) -> dict:
    payload = _json_dict(task.source_payload_json)
    explicit_steps = _extract_plan_steps(payload)
    tool_name = payload.get("tool_name") or payload.get("requested_tool")
    arguments = payload.get("arguments")
    if arguments is None:
        arguments = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

    if bool(task.requires_human_confirmation):
        return {
            "action": "handoff",
            "reason": "human_confirmation_required",
            "payload": payload,
        }
    if explicit_steps:
        return {
            "action": "execute_plan",
            "steps": explicit_steps,
            "reason": "explicit_tool_sequence",
            "confidence": 1,
            "payload": payload,
        }
    if tool_name:
        return {
            "action": "execute_tool",
            "tool_name": str(tool_name),
            "arguments": arguments if isinstance(arguments, dict) else {},
            "payload": payload,
        }
    sop_plan = build_sop_plan(task, payload)
    if sop_plan is not None:
        return sop_plan
    if payload.get("kernel_intent") in {"reader_ai_chat", "business_event"}:
        return {
            "action": "complete",
            "reason": str(payload.get("kernel_intent")),
            "payload": payload,
        }
    client = _client(llm_client)
    if _engine_ready(client):
        try:
            plan = call_json_schema(
                client,
                messages=_planner_messages(db, task, payload),
                schema=KernelTaskPlan,
                label="kernel_task_plan",
                temperature=0,
            )
            data = plan.model_dump(mode="json")
            data["payload"] = payload
            if data["action"] == "execute_plan":
                data["steps"] = _extract_plan_steps(data)
                if not data["steps"]:
                    return _fallback_plan(task, payload)
                data["tool_name"] = ""
                data["arguments"] = {}
            elif data["action"] != "execute_tool":
                data["tool_name"] = ""
                data["arguments"] = {}
                data["steps"] = []
            return data
        except Exception:
            return _fallback_plan(task, payload)
    return _fallback_plan(task, payload)


def _plan_to_steps(plan: dict) -> list[dict]:
    if plan["action"] == "execute_plan":
        return _extract_plan_steps(plan)
    if plan["action"] == "execute_tool":
        return [
            {
                "tool_name": plan["tool_name"],
                "arguments": plan["arguments"],
                "reason": plan.get("reason", "dynamic_single_tool_execution"),
                "stop_on_failure": True,
            }
        ]
    return []


def _process_dynamic_loop(
    db: Session,
    task: WorkTask,
    run: AgentRun,
    *,
    initial_plan: dict,
    worker_id: str,
    llm_client=None,
) -> tuple[WorkTask, dict]:
    plans = [initial_plan]
    plan = initial_plan
    observations: list[dict] = []
    tool_results: list[dict] = []

    for iteration in range(1, MAX_DYNAMIC_ITERATIONS + 1):
        if plan["action"] == "complete":
            result = {
                "status": "success",
                "message": "AI Kernel dynamic loop completed.",
                "tool_results": tool_results,
                "observations": observations,
                "plans": plans,
            }
            task = ai_complete_task(db, task.task_code, run_id=run.id, result=as_json(result), actor_id=worker_id, commit=False)
            output = {"status": "success", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, **result}
            run.status = "success"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="dynamic_complete", status="success", state=output)
            _write_step(db, run, "dynamic_complete", "success", output)
            return task, output

        if plan["action"] == "handoff":
            task = interrupt_task(db, task.task_code, reason=plan["reason"], actor_id=worker_id, commit=False)
            output = {"status": "waiting_human", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, "tool_results": tool_results, "observations": observations}
            run.status = "waiting_human"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="dynamic_handoff", status="waiting_human", state=output)
            _write_step(db, run, "dynamic_handoff", "waiting_human", output)
            return task, output

        steps = _plan_to_steps(plan)
        if not steps:
            task = interrupt_task(db, task.task_code, reason="dynamic_loop_empty_plan", actor_id=worker_id, commit=False)
            output = {"status": "waiting_human", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, "tool_results": tool_results, "observations": observations}
            run.status = "waiting_human"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="dynamic_empty_plan", status="waiting_human", state=output)
            _write_step(db, run, "dynamic_empty_plan", "waiting_human", output)
            return task, output

        step = steps[0]
        tool_name = str(step.get("tool_name") or "").strip()
        arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        step_detail = {"iteration": iteration, "tool_name": tool_name, "arguments": arguments, "reason": step.get("reason")}
        try:
            result = dispatch_tool(
                db,
                tool_name,
                arguments,
                actor_id=worker_id,
                run_id=run.id,
                planner_context=True,
                task=task,
                autonomous=True,
            )
        except Exception as exc:
            task = interrupt_task(db, task.task_code, reason=f"dynamic_tool_execution_error:{tool_name}: {exc}", actor_id=worker_id, commit=False)
            output = {"status": "waiting_human", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, "tool_results": tool_results, "observations": observations, "failed_step": step_detail, "error": str(exc)}
            run.status = "waiting_human"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"dynamic_tool_error_{iteration}", status="waiting_human", state=output)
            _write_step(db, run, f"dynamic_tool_error_{iteration}", "waiting_human", output)
            return task, output

        record = {**step_detail, "status": result["status"], "result": result}
        tool_results.append(record)
        observations.append({"iteration": iteration, "plan": plan, "executed_step": step_detail, "result": result, "remaining_planned_steps": steps[1:]})
        _write_step(db, run, f"dynamic_tool_{iteration}_{tool_name}", result["status"], record)
        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"dynamic_tool_{iteration}", status=result["status"], state=record)

        if result["status"] == "waiting_authorization":
            task = interrupt_task(db, task.task_code, reason=f"dynamic_tool_waiting_authorization:{tool_name}", actor_id=worker_id, commit=False)
            output = {"status": "waiting_authorization", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, "tool_results": tool_results, "observations": observations, "waiting_step": step_detail}
            run.status = "waiting_authorization"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"dynamic_authorization_{iteration}", status="waiting_authorization", state=output)
            return task, output

        if result["status"] == "needs_clarification":
            task = interrupt_task(db, task.task_code, reason=f"dynamic_tool_needs_clarification:{tool_name}", actor_id=worker_id, commit=False)
            output = {
                "status": "needs_clarification",
                "task": task_to_dict(task),
                "plan": {"action": "dynamic_agent_loop", "plans": plans},
                "tool_results": tool_results,
                "observations": observations,
                "waiting_step": step_detail,
                "missing_fields": result.get("missing_fields", []),
            }
            run.status = "needs_clarification"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_plan_json = as_json(output["plan"])
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"dynamic_clarification_{iteration}", status="needs_clarification", state=output)
            return task, output

        payload = _json_dict(task.source_payload_json)
        payload["dynamic_agent_loop"] = True
        payload["dynamic_observations"] = observations
        payload["completed_tool_steps"] = tool_results
        payload["last_planned_remaining_steps"] = steps[1:]
        task.source_payload_json = as_json(payload)
        context = _json_dict(task.execution_context_json)
        context["dynamic_observations"] = observations
        task.execution_context_json = as_json(context)

        plan = _plan_task(db, task, llm_client=llm_client)
        plans.append(plan)
        task.ai_plan_json = as_json({"action": "dynamic_agent_loop", "plans": plans})
        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"dynamic_replan_{iteration}", status=plan["action"], state=plan)
        _write_step(db, run, f"dynamic_replan_{iteration}", plan["action"], plan)

    task = interrupt_task(db, task.task_code, reason="dynamic_loop_max_iterations", actor_id=worker_id, commit=False)
    output = {"status": "waiting_human", "task": task_to_dict(task), "plan": {"action": "dynamic_agent_loop", "plans": plans}, "tool_results": tool_results, "observations": observations}
    run.status = "waiting_human"
    run.output_json = as_json(output)
    run.finished_at = now()
    run.updated_at = now()
    task.ai_plan_json = as_json(output["plan"])
    task.ai_trace_json = as_json(output)
    write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="dynamic_max_iterations", status="waiting_human", state=output)
    _write_step(db, run, "dynamic_max_iterations", "waiting_human", output)
    return task, output


def process_task(
    db: Session,
    task_code: str,
    *,
    worker_id: str = "ai-kernel-worker",
    lease_seconds: int = 300,
    commit: bool = True,
    llm_client=None,
) -> dict:
    task = get_task(db, task_code)
    run: AgentRun | None = None
    try:
        run = AgentRun(
            run_code=_run_code(),
            trigger_type="task_pool",
            actor_type="ai_admin",
            actor_code=worker_id,
            tool_name="ai_kernel_task_agent",
            status="running",
            input_json=as_json({"task": task_to_dict(task)}),
            started_at=now(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(run)
        db.flush()

        task = _ensure_claimed(db, task, worker_id=worker_id, run_id=run.id, lease_seconds=lease_seconds)
        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="claim", status="success", state=task_to_dict(task))
        _write_step(db, run, "claim", "success", {"task_code": task.task_code, "lease_owner": task.lease_owner})

        execution_context = {
            "task": task_to_dict(task),
            "source_payload": _json_dict(task.source_payload_json),
            "execution_context": _json_dict(task.execution_context_json),
        }
        task.execution_context_json = as_json(execution_context)
        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="context", status="success", state=execution_context)
        _write_step(db, run, "context", "success", execution_context)

        source_payload = _json_dict(task.source_payload_json)
        if should_split_task(source_payload):
            plan = {
                "action": "split_tasks",
                "reason": "multi_intent_task_package",
                "confidence": 1,
                "payload": source_payload,
            }
            task.ai_plan_json = as_json(plan)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="plan", status="split_tasks", state=plan)
            _write_step(db, run, "plan", "split_tasks", plan)

            package = create_task_package_children(db, task, actor_id=worker_id, limit=MAX_SPLIT_SUBTASKS)
            child_results: list[dict] = []
            tool_results: list[dict] = []
            followup_results: list[dict] = []
            blocked: dict | None = None
            if bool(source_payload.get("process_subtasks_immediately")):
                for child in db.scalars(select(WorkTask).where(WorkTask.source_task_id == task.id).order_by(WorkTask.id.asc())).all():
                    child_payload = _json_dict(child.source_payload_json)
                    if child_payload.get("task_package_id") != package["task_package_id"]:
                        continue
                    child_result = process_task(db, child.task_code, worker_id=worker_id, lease_seconds=lease_seconds, commit=False, llm_client=llm_client)
                    child_output = _run_output(db, child_result.get("run_id"))
                    child_record = {
                        "task_code": child.task_code,
                        "status": child_result["status"],
                        "result": child_result,
                        "output": child_output,
                    }
                    child_results.append(child_record)
                    tool_results.extend(child_output.get("tool_results") or [])
                    followup_results.extend(child_output.get("followup_results") or [])
                    if child_result["status"] != "success":
                        blocked = child_record
                        break

            if blocked is not None:
                block_status = str(blocked.get("status") or "waiting_human")
                task = interrupt_task(db, task.task_code, reason=f"subtask_blocked:{block_status}:{blocked['task_code']}", actor_id=worker_id, commit=False)
                output = {
                    "status": block_status,
                    "task": task_to_dict(task),
                    "plan": plan,
                    "task_package": package,
                    "child_results": child_results,
                    "tool_results": tool_results,
                    "followup_results": followup_results,
                    "blocked_child": blocked,
                }
                run.status = block_status
                run.output_json = as_json(output)
                run.finished_at = now()
                run.updated_at = now()
                task.ai_trace_json = as_json(output)
                write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="split_blocked", status=block_status, state=output)
                _write_step(db, run, "split_blocked", block_status, output)
            else:
                result = {
                    "status": "success",
                    "message": "AI Kernel split the multi-intent task package.",
                    "task_package": package,
                    "child_results": child_results,
                    "tool_results": tool_results,
                    "followup_results": followup_results,
                }
                task = ai_complete_task(db, task.task_code, run_id=run.id, result=as_json(result), actor_id=worker_id, commit=False)
                output = {"status": "success", "task": task_to_dict(task), "plan": plan, **result}
                run.status = "success"
                run.output_json = as_json(output)
                run.finished_at = now()
                run.updated_at = now()
                task.ai_trace_json = as_json(output)
                write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="split_tasks", status="success", state=output)
                _write_step(db, run, "split_tasks", "success", output)

            write_audit(
                db,
                actor_type="ai_admin",
                actor_id=worker_id,
                action="ai_kernel_process_task",
                target_table="work_tasks",
                target_id=task.task_code,
                detail={"run_id": run.id, "status": run.status, "plan_action": plan["action"]},
            )
            if commit:
                db.commit()
                db.refresh(task)
                db.refresh(run)
            return {"run_code": run.run_code, "run_id": run.id, "status": run.status, "task": task_to_dict(task)}

        plan = _plan_task(db, task, llm_client=llm_client)
        task.ai_plan_json = as_json(plan)
        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="plan", status=plan["action"], state=plan)
        _write_step(db, run, "plan", plan["action"], plan)

        if bool(_json_dict(task.source_payload_json).get("dynamic_agent_loop")):
            task, output = _process_dynamic_loop(db, task, run, initial_plan=plan, worker_id=worker_id, llm_client=llm_client)
        elif plan["action"] == "handoff":
            task = interrupt_task(db, task.task_code, reason=plan["reason"], actor_id=worker_id, commit=False)
            output = {"status": "waiting_human", "task": task_to_dict(task), "plan": plan}
            run.status = "waiting_human"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="handoff", status="waiting_human", state=output)
            _write_step(db, run, "handoff", "waiting_human", output)
        elif plan["action"] in {"execute_tool", "execute_plan"}:
            steps = (
                plan.get("steps") or []
                if plan["action"] == "execute_plan"
                else [{"tool_name": plan["tool_name"], "arguments": plan["arguments"], "reason": plan.get("reason", "single_tool_execution"), "stop_on_failure": True}]
            )
            tool_results: list[dict] = []
            output: dict | None = None
            if not steps:
                task = interrupt_task(db, task.task_code, reason="empty_executable_plan", actor_id=worker_id, commit=False)
                output = {"status": "waiting_human", "task": task_to_dict(task), "plan": plan}
                run.status = "waiting_human"
                run.output_json = as_json(output)
                run.finished_at = now()
                run.updated_at = now()
                task.ai_trace_json = as_json(output)
                write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="empty_plan", status="waiting_human", state=output)
                _write_step(db, run, "empty_plan", "waiting_human", output)
                steps = []
            for index, step in enumerate(steps[:MAX_SPLIT_SUBTASKS], start=1):
                tool_name = str(step.get("tool_name") or "").strip()
                arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
                step_detail = {"step_index": index, "tool_name": tool_name, "arguments": arguments, "reason": step.get("reason")}
                try:
                    result = dispatch_tool(
                        db,
                        tool_name,
                        arguments,
                        actor_id=worker_id,
                        run_id=run.id,
                        planner_context=True,
                        task=task,
                        autonomous=True,
                    )
                except Exception as exc:
                    task = interrupt_task(db, task.task_code, reason=f"tool_execution_error:{tool_name}: {exc}", actor_id=worker_id, commit=False)
                    output = {"status": "waiting_human", "task": task_to_dict(task), "plan": plan, "tool_results": tool_results, "failed_step": step_detail, "error": str(exc)}
                    run.status = "waiting_human"
                    run.output_json = as_json(output)
                    run.finished_at = now()
                    run.updated_at = now()
                    task.ai_trace_json = as_json(output)
                    write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"tool_error_{index}", status="waiting_human", state=output)
                    _write_step(db, run, f"tool_error_{index}", "waiting_human", output)
                    break

                record = {**step_detail, "status": result["status"], "result": result}
                tool_results.append(record)
                _write_step(db, run, f"tool_{index}_{tool_name}", result["status"], record)
                write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"tool_{index}", status=result["status"], state=record)

                if result["status"] == "waiting_authorization":
                    task = interrupt_task(db, task.task_code, reason=f"tool_waiting_authorization:{tool_name}", actor_id=worker_id, commit=False)
                    output = {"status": "waiting_authorization", "task": task_to_dict(task), "plan": plan, "tool_results": tool_results, "waiting_step": step_detail}
                    run.status = "waiting_authorization"
                    run.output_json = as_json(output)
                    run.finished_at = now()
                    run.updated_at = now()
                    task.ai_trace_json = as_json(output)
                    write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"authorization_{index}", status="waiting_authorization", state=output)
                    break
                if result["status"] == "needs_clarification":
                    task = interrupt_task(db, task.task_code, reason=f"tool_needs_clarification:{tool_name}", actor_id=worker_id, commit=False)
                    output = {
                        "status": "needs_clarification",
                        "task": task_to_dict(task),
                        "plan": plan,
                        "tool_results": tool_results,
                        "waiting_step": step_detail,
                        "missing_fields": result.get("missing_fields", []),
                    }
                    run.status = "needs_clarification"
                    run.output_json = as_json(output)
                    run.finished_at = now()
                    run.updated_at = now()
                    task.ai_trace_json = as_json(output)
                    write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"clarification_{index}", status="needs_clarification", state=output)
                    break

            if output is None:
                outcome = evaluate_execution_outcome(task, plan, tool_results)
                followup_results: list[dict] = []
                followup_steps = build_followup_steps(task, plan, outcome, tool_results)
                for followup_index, step in enumerate(followup_steps, start=1):
                    tool_name = str(step.get("tool_name") or "").strip()
                    arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
                    idempotency_key = str(step.get("idempotency_key") or "").strip() or default_idempotency_key(
                        task,
                        sop_id=str(plan.get("sop_id") or outcome.get("sop_id") or ""),
                        phase="followup",
                        tool_name=tool_name,
                        arguments=arguments,
                    )
                    target_type = str(step.get("target_type") or "").strip()
                    target_id = str(step.get("target_id") or "").strip()
                    step_detail = {
                        "step_index": len(tool_results) + 1,
                        "followup_index": followup_index,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "reason": step.get("reason"),
                        "followup": True,
                        "idempotency_key": idempotency_key,
                        "target_type": target_type,
                        "target_id": target_id,
                    }
                    completed = completed_execution(db, idempotency_key)
                    if completed is not None:
                        result = ledger_to_skipped_result(completed)
                        record = {**step_detail, "status": result["status"], "result": result}
                        followup_results.append(record)
                        tool_results.append(record)
                        _write_step(db, run, f"followup_{followup_index}_{tool_name}", result["status"], record)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"followup_{followup_index}", status=result["status"], state=record)
                        continue
                    try:
                        result = dispatch_tool(
                            db,
                            tool_name,
                            arguments,
                            actor_id=worker_id,
                            run_id=run.id,
                            planner_context=True,
                            task=task,
                            autonomous=True,
                        )
                    except Exception as exc:
                        record_execution_attempt(
                            db,
                            task=task,
                            run_id=run.id,
                            sop_id=str(plan.get("sop_id") or outcome.get("sop_id") or ""),
                            phase="followup",
                            tool_name=tool_name,
                            idempotency_key=idempotency_key,
                            target_type=target_type,
                            target_id=target_id,
                            arguments=arguments,
                            result={"error": str(exc)},
                            status="failed",
                            reason="followup_tool_execution_error",
                        )
                        task = interrupt_task(db, task.task_code, reason=f"followup_tool_execution_error:{tool_name}: {exc}", actor_id=worker_id, commit=False)
                        output = {
                            "status": "waiting_human",
                            "task": task_to_dict(task),
                            "plan": plan,
                            "tool_results": tool_results,
                            "followup_results": followup_results,
                            "outcome": outcome,
                            "failed_step": step_detail,
                            "error": str(exc),
                        }
                        run.status = "waiting_human"
                        run.output_json = as_json(output)
                        run.finished_at = now()
                        run.updated_at = now()
                        task.ai_trace_json = as_json(output)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"followup_error_{followup_index}", status="waiting_human", state=output)
                        _write_step(db, run, f"followup_error_{followup_index}", "waiting_human", output)
                        break

                    record = {**step_detail, "status": result["status"], "result": result}
                    record_execution_attempt(
                        db,
                        task=task,
                        run_id=run.id,
                        sop_id=str(plan.get("sop_id") or outcome.get("sop_id") or ""),
                        phase="followup",
                        tool_name=tool_name,
                        idempotency_key=idempotency_key,
                        target_type=target_type,
                        target_id=target_id,
                        arguments=arguments,
                        result=result,
                        status="completed" if result["status"] == "success" else str(result["status"]),
                        reason=str(step.get("reason") or ""),
                    )
                    followup_results.append(record)
                    tool_results.append(record)
                    _write_step(db, run, f"followup_{followup_index}_{tool_name}", result["status"], record)
                    write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"followup_{followup_index}", status=result["status"], state=record)

                    if result["status"] == "waiting_authorization":
                        task = interrupt_task(db, task.task_code, reason=f"followup_tool_waiting_authorization:{tool_name}", actor_id=worker_id, commit=False)
                        output = {
                            "status": "waiting_authorization",
                            "task": task_to_dict(task),
                            "plan": plan,
                            "tool_results": tool_results,
                            "followup_results": followup_results,
                            "outcome": outcome,
                            "waiting_step": step_detail,
                        }
                        run.status = "waiting_authorization"
                        run.output_json = as_json(output)
                        run.finished_at = now()
                        run.updated_at = now()
                        task.ai_trace_json = as_json(output)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"followup_authorization_{followup_index}", status="waiting_authorization", state=output)
                        break
                    if result["status"] == "needs_clarification":
                        task = interrupt_task(db, task.task_code, reason=f"followup_tool_needs_clarification:{tool_name}", actor_id=worker_id, commit=False)
                        output = {
                            "status": "needs_clarification",
                            "task": task_to_dict(task),
                            "plan": plan,
                            "tool_results": tool_results,
                            "followup_results": followup_results,
                            "outcome": outcome,
                            "waiting_step": step_detail,
                            "missing_fields": result.get("missing_fields", []),
                        }
                        run.status = "needs_clarification"
                        run.output_json = as_json(output)
                        run.finished_at = now()
                        run.updated_at = now()
                        task.ai_trace_json = as_json(output)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name=f"followup_clarification_{followup_index}", status="needs_clarification", state=output)
                        break

                outcome["followup_steps"] = len(followup_results)
                if output is None:
                    if outcome["decision"] == "handoff":
                        task = interrupt_task(db, task.task_code, reason=outcome["reason"], actor_id=worker_id, commit=False)
                        output = {"status": "waiting_human", "task": task_to_dict(task), "plan": plan, "tool_results": tool_results, "followup_results": followup_results, "outcome": outcome}
                        run.status = "waiting_human"
                        run.output_json = as_json(output)
                        run.finished_at = now()
                        run.updated_at = now()
                        task.ai_trace_json = as_json(output)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="outcome", status="waiting_human", state=output)
                        _write_step(db, run, "outcome", "waiting_human", output)
                    else:
                        result = {"status": "success", "message": "AI Kernel executed planned tool steps.", "tool_results": tool_results, "outcome": outcome}
                        task = ai_complete_task(db, task.task_code, run_id=run.id, result=as_json(result), actor_id=worker_id, commit=False)
                        output = {"status": "success", "task": task_to_dict(task), "plan": plan, "tool_results": tool_results, "followup_results": followup_results, "outcome": outcome}
                        run.status = "success"
                        run.output_json = as_json(output)
                        run.finished_at = now()
                        run.updated_at = now()
                        task.ai_trace_json = as_json(output)
                        write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="execute", status="success", state=output)
        else:
            result = {"status": "success", "message": "AI Kernel completed low-risk administrative task."}
            task = ai_complete_task(db, task.task_code, run_id=run.id, result=as_json(result), actor_id=worker_id, commit=False)
            output = {"status": "success", "task": task_to_dict(task), "plan": plan, "result": result}
            run.status = "success"
            run.output_json = as_json(output)
            run.finished_at = now()
            run.updated_at = now()
            task.ai_trace_json = as_json(output)
            write_checkpoint(db, task=task, run_id=run.id, worker_id=worker_id, node_name="complete", status="success", state=output)
            _write_step(db, run, "complete", "success", output)

        write_audit(
            db,
            actor_type="ai_admin",
            actor_id=worker_id,
            action="ai_kernel_process_task",
            target_table="work_tasks",
            target_id=task.task_code,
            detail={"run_id": run.id, "status": run.status, "plan_action": plan["action"]},
        )
        if commit:
            db.commit()
            db.refresh(task)
            db.refresh(run)
        return {"run_code": run.run_code, "run_id": run.id, "status": run.status, "task": task_to_dict(task)}
    except Exception as exc:
        if run is not None:
            run.status = "failed"
            run.output_json = as_json({"error": str(exc), "task_code": task_code})
            run.finished_at = now()
            run.updated_at = now()
            _write_step(db, run, "error", "failed", {"error": str(exc), "task_code": task_code})
        try:
            failed_task = handle_task_failure(
                db,
                task_code,
                worker_id=worker_id,
                reason=str(exc),
                run_id=run.id if run is not None else None,
                commit=False,
            )
            if run is not None:
                run.output_json = as_json({"error": str(exc), "task_code": task_code, "task": task_to_dict(failed_task)})
        except Exception:
            pass
        if commit:
            db.commit()
        raise


def process_next_task(
    db: Session,
    *,
    worker_id: str = "ai-kernel-worker",
    queue_name: str | None = None,
    lease_seconds: int = 300,
    commit: bool = True,
    llm_client=None,
) -> dict:
    refresh_queue(db, limit=500, commit=False)
    task = lease_next_task(db, worker_id=worker_id, queue_name=queue_name, lease_seconds=lease_seconds, commit=False)
    if task is None:
        if commit:
            db.commit()
        return {"status": "idle", "task": None}
    record_task_event(
        db,
        task,
        event_type="ai_kernel_dispatch_task",
        actor_type="ai",
        actor_id=worker_id,
        detail={"queue_name": task.queue_name},
    )
    if commit:
        db.commit()
        db.refresh(task)
    return process_task(db, task.task_code, worker_id=worker_id, lease_seconds=lease_seconds, commit=commit, llm_client=llm_client)
