from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool


class FileWriteTool(Tool):
    spec = ToolSpec(
        name="file_write",
        description="write a file inside allowed roots",
        input_schema={"type": "object", "required": ["path", "text"]},
        side_effect_level="medium",
        requires_confirmation=True,
        allowed_in_idle=False,
        reversibility="partial",
        observability="high",
        blast_radius="medium",
        audit_required=True,
    )

    def __init__(self, allowed_roots: list[str]) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        path = Path(call.arguments["path"]).resolve()
        if not any(str(path).startswith(str(root)) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(call.arguments["text"], encoding="utf-8")
        return ToolResult(ok=True, output={"written": True, "path": str(path)})
