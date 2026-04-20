from __future__ import annotations

import time

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.registry import ToolRegistry
from subjective_runtime_v2_1.state.models import ActionOption


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
        result = self.registry.invoke(call, ctx)
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "ok" if result.ok else "error",
            "tool_name": call.tool_name,
            "arguments": call.arguments,
            "result": result.output,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }
