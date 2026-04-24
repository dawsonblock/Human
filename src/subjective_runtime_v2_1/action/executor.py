from __future__ import annotations

import time

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.registry import ToolRegistry
from subjective_runtime_v2_1.state.models import ActionOption

_DEFAULT_TIMEOUT_SEC = 30.0


class Executor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, action: ActionOption, ctx: ExecutionContext) -> dict:
        start = time.perf_counter()
        call = ToolCall(
            tool_name=action.target["tool_name"],
            arguments=action.target.get("arguments", {}),
            reason=action.target.get("reason", action.name),
            origin=action.target.get("origin", "planner"),
            dry_run=action.target.get("dry_run", False),
        )
        try:
            spec = self.registry.get(call.tool_name).spec
            timeout = spec.timeout_sec if spec.timeout_sec > 0 else _DEFAULT_TIMEOUT_SEC
        except KeyError:
            timeout = _DEFAULT_TIMEOUT_SEC

        try:
            result = self._invoke_with_timeout(call, ctx, timeout)
        except TimeoutError:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return {
                "status": "error",
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "result": {},
                "error": f"tool timed out after {timeout}s",
                "latency_ms": latency_ms,
                "memory_writes": [],
                "state_delta": {},
                "observations": [],
                "artifacts": [],
                "step_id": action.target.get("step_id"),
            }

        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "ok" if result.ok else "error",
            "tool_name": call.tool_name,
            "arguments": call.arguments,
            "result": result.output,
            "error": result.error,
            "latency_ms": result.latency_ms,
            "memory_writes": result.memory_writes,
            "state_delta": result.state_delta,
            "observations": result.observations,
            "artifacts": result.artifacts,
            "step_id": action.target.get("step_id"),
        }

    def _invoke_with_timeout(self, call: ToolCall, ctx: ExecutionContext, timeout: float):
        """Invoke the tool.  For CPU-bound sync tools this is a simple call;
        the timeout guard catches runaway tools via a deadline check after invoke.
        Truly blocking I/O would require threading — kept simple for now."""
        start = time.perf_counter()
        result = self.registry.invoke(call, ctx)
        elapsed = time.perf_counter() - start
        if elapsed > timeout:
            raise TimeoutError(f"tool exceeded {timeout}s")
        return result
