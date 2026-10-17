from __future__ import annotations

from bookflow_core.services.common import as_json


AI_ADMIN_SYSTEM_PROMPT = """
You are the BookFlow high-permission AI administrator.
Authority order: super_admin > ai_admin > admin > reader > guest.
You can handle routine library operations, but you are below the super administrator.
You must obey L0-L5 permissions.
You must never execute arbitrary SQL, delete audit logs, read API keys, self-escalate, or disable super administrators.
You must use controlled BookFlow Core tools only.
You must not bypass permission checks, policy guard, audit logs, snapshots, or human authorization.
Only L4 or explicitly super-authorization tools must create a super administrator approval.
Business risk levels control audit strength, confirmation, retry, and trace detail; high risk alone is not a reason to refuse a registered tool.
L5 actions must be refused.
All outputs must be strict JSON objects matching the requested schema.
Task decisions and tool calls must be grounded in BookFlow data and task context.
Do not invent tasks, data, book records, readers, copies, or statistics.
If required tool arguments are missing or ambiguous, ask for the missing information instead of guessing identifiers.
Do not present advice as an executed result.
""".strip()


def build_chat_plan_messages(*, recent_messages: list[dict], current_text: str, tool_schemas: list[dict], recent_kernel_runs: list[dict]) -> list[dict]:
    schema_instruction = """Decide how to answer a BookFlow admin chat message.
First rewrite the latest user message into a standalone_request that can be understood without
reading the chat history. Resolve pronouns, ellipsis, follow-up words, "more", "continue",
"check all of that", and similar references from recent_messages. If the latest message is too
ambiguous even with history, use direct_answer and ask one specific clarifying question.

Return ONLY a JSON object with exactly these fields:
{
  "intent": "direct_answer" | "tool_call" | "kernel_patrol",
  "standalone_request": "<self-contained version of the user's latest request>",
  "tool_calls": [{"tool_name": "<registered tool name>", "arguments": {}, "reason": "<why this tool is needed>"}],
  "patrol": null,
  "reply": "<your direct reply text when intent is direct_answer>",
  "llm_summary": "<one-line summary of your reasoning>",
  "model_name": "<the model you are running as>"
}
- For simple greetings or questions: use "direct_answer" with a helpful reply and empty tool_calls.
- For data queries: use "tool_call" and list the tools to call.
- For patrol/audit requests: use "kernel_patrol".
- Tool arguments must be grounded in standalone_request plus available chat history; never use vague
  placeholders like "that", "above", "previous result", or empty keywords when a concrete value can
  be resolved from recent_messages.
- For catalog questions about titles, authors, ISBNs, genres, subjects, series, "do we have ...",
  availability, copy counts, or shelf locations: use ai_search_books. Pass the user's natural phrase
  as keyword; the backend search normalizes series/genre/fuzzy wording.
- If the user challenges a previous catalog result, re-query with a broader/raw phrase instead of
  defending the previous answer from memory.
- If the user asks for an operation that has no registered tool, say exactly what is unavailable and
  where the admin can handle it in BookFlow; do not invent permissions or claim super-admin approval
  is needed unless a registered tool reports authorization_required.
- Use tools only when the required arguments are concrete enough; otherwise reply with the specific missing fields.
- Always include llm_summary and model_name.
- Do NOT use "plan_type", "response", or any other field names not listed above.
- Do NOT add extra fields."""
    return [
        {"role": "system", "content": AI_ADMIN_SYSTEM_PROMPT},
        {"role": "system", "content": schema_instruction},
        {"role": "system", "content": as_json({"available_tools": tool_schemas, "recent_kernel_runs": recent_kernel_runs})},
        *recent_messages,
        {"role": "user", "content": current_text},
    ]


def build_chat_reply_messages(*, current_text: str, plan: dict, tool_results: list[dict], kernel_result: dict | None) -> list[dict]:
    return [
        {"role": "system", "content": AI_ADMIN_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "Compose the final user-facing reply in natural Chinese. Return JSON object {'reply': string}. "
                "Use standalone_request from chat_plan to explain what was checked when it differs from the raw user text. "
                "Use only tool_results/kernel_result as factual data. For ai_search_books, mention the normalized query "
                "or expansion when it differs from the user's wording, distinguish total matches from returned items, "
                "and name titles with authors/copy availability when present. If an item has metadata_only_match or notes, "
                "say it matched catalog metadata such as category/keywords, not that the literary fact is certainly true. "
                "If results are empty, give useful next search terms from empty_suggestions and do not pretend the library lacks the subject absolutely."
            ),
        },
        {
            "role": "user",
            "content": as_json(
                {
                    "user_text": current_text,
                    "chat_plan": plan,
                    "tool_results": tool_results,
                    "kernel_result": kernel_result,
                }
            ),
        },
    ]
