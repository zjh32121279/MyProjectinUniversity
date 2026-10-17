from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bookflow_core.core.config import AI_ENGINE_ENV_KEYS, ai_engine_config
from bookflow_core.core.exceptions import BookFlowError


@dataclass(frozen=True)
class AIEngineStatus:
    enabled: bool
    configured: bool
    available: bool
    connected: bool
    ok: bool
    base_url: str | None
    model: str | None
    reason: str
    required_env: list[str]
    missing_env: list[str]


def _not_configured_error(missing: list[str]) -> BookFlowError:
    return BookFlowError(
        "BookFlow AI engine is not configured. AI administrator features are unavailable.",
        code="AI_ENGINE_NOT_CONFIGURED",
        details={"required_env": list(AI_ENGINE_ENV_KEYS), "missing_env": missing},
    )


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = 300,
    ):
        config = ai_engine_config()
        self.base_url = base_url if base_url is not None else config["base_url"]
        self.model = model if model is not None else config["model"]
        self.api_key = api_key if api_key is not None else config["api_key"]
        self.timeout_seconds = timeout_seconds

    def _missing_env(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("BOOKFLOW_AI_ENGINE_BASE_URL")
        if not self.api_key:
            missing.append("BOOKFLOW_AI_ENGINE_API_KEY")
        if not self.model:
            missing.append("BOOKFLOW_AI_ENGINE_NAME")
        return missing

    def status(self) -> AIEngineStatus:
        missing = self._missing_env()
        configured = not missing
        return AIEngineStatus(
            enabled=configured,
            configured=configured,
            available=configured,
            connected=configured,
            ok=configured,
            base_url=self.base_url,
            model=self.model,
            reason="ready" if configured else "missing_env",
            required_env=list(AI_ENGINE_ENV_KEYS),
            missing_env=missing,
        )

    def probe_models(self, *, timeout_seconds: int = 8) -> dict:
        missing = self._missing_env()
        if missing:
            return {"checked": True, "ok": False, "reason": "missing_env", "missing_env": missing}
        assert self.base_url is not None
        assert self.api_key is not None
        request = Request(
            f"{self.base_url.rstrip('/')}/models",
            method="GET",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with self._open(request, timeout=min(timeout_seconds, 8)) as response:
                response.read(256)
            return {"checked": True, "ok": True, "reason": "ready"}
        except HTTPError as exc:
            return {"checked": True, "ok": False, "reason": "http_error", "status_code": exc.code}
        except TimeoutError:
            return {"checked": True, "ok": False, "reason": "timeout"}
        except socket.timeout:
            return {"checked": True, "ok": False, "reason": "timeout"}
        except URLError as exc:
            reason = type(exc.reason).__name__ if hasattr(exc, "reason") else "url_error"
            return {"checked": True, "ok": False, "reason": "url_error", "detail": str(reason)}

    def require_ready(self) -> None:
        missing = self._missing_env()
        if missing:
            raise _not_configured_error(missing)

    def _open(self, request: Request, timeout: int):
        return urlopen(request, timeout=timeout)

    def complete_text(self, *, messages: list[dict], temperature: float = 0.1, json_mode: bool = False) -> str:
        self.require_ready()
        assert self.base_url is not None
        assert self.model is not None
        assert self.api_key is not None
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._open(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise BookFlowError(
                "BookFlow AI engine request failed.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"status_code": exc.code},
            ) from exc
        except URLError as exc:
            reason = type(exc.reason).__name__ if hasattr(exc, "reason") else "url_error"
            raise BookFlowError(
                "BookFlow AI engine is unavailable.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"reason": reason},
            ) from exc
        except TimeoutError as exc:
            raise BookFlowError(
                "BookFlow AI engine request timed out.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"reason": "timeout"},
            ) from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise BookFlowError(
                "BookFlow AI engine returned an invalid response.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"reason": "invalid_engine_response"},
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise BookFlowError(
                "BookFlow AI engine returned an empty response.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"reason": "empty_engine_response"},
            )
        return content

    def complete_json(self, *, messages: list[dict], temperature: float = 0.1) -> dict:
        try:
            content = self.complete_text(messages=messages, temperature=temperature, json_mode=True)
        except BookFlowError as exc:
            if exc.code != "AI_ENGINE_UNAVAILABLE" or exc.details.get("status_code") != 400:
                raise
            fallback_messages = [
                {
                    "role": "system",
                    "content": "只返回 JSON 对象，不要 Markdown，不要解释，不要代码块。",
                },
                *messages,
            ]
            content = self.complete_text(messages=fallback_messages, temperature=temperature, json_mode=False)
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise BookFlowError(
                "BookFlow AI planner output is not valid JSON.",
                code="AI_PLANNER_OUTPUT_INVALID",
                details={"reason": "json_parse_failed", "raw_prefix": stripped[:200]},
            ) from exc
        if not isinstance(data, dict):
            raise BookFlowError(
                "BookFlow AI planner output must be a JSON object.",
                code="AI_PLANNER_OUTPUT_INVALID",
                details={"reason": "json_object_required"},
            )
        return data

    def rewrite(self, *, messages: list[dict], current_text: str) -> str:
        prompt = [
            {
                "role": "system",
                "content": (
                    "You rewrite BookFlow chat follow-up questions only from conversation context. "
                    "Return plain rewritten text and do not execute tools."
                ),
            },
            *messages,
            {"role": "user", "content": current_text},
        ]
        return self.complete_text(messages=prompt, temperature=0).strip()


def ai_engine_status(*, probe: bool = False) -> dict:
    client = OpenAICompatibleClient()
    status = client.status()
    probe_result = client.probe_models(timeout_seconds=8) if probe else {"checked": False, "ok": status.connected, "reason": "not_requested"}
    connected = bool(probe_result.get("ok")) if probe else status.connected
    reason = "ready" if connected else str(probe_result.get("reason") or status.reason)
    return {
        "enabled": status.enabled,
        "configured": status.configured,
        "available": connected,
        "connected": connected,
        "ok": connected,
        "base_url": status.base_url,
        "model": status.model,
        "reason": reason,
        "required_env": status.required_env,
        "missing_env": status.missing_env,
        "probe": probe_result,
    }
