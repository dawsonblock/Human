from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool


class FileReadTool(Tool):
    spec = ToolSpec(
        name="file_read",
        description="read a file from allowed roots",
        input_schema={"type": "object", "required": ["path"]},
        side_effect_level="low",
        allowed_in_idle=True,
        reversibility="full",
        observability="high",
        blast_radius="low",
    )

    def __init__(self, allowed_roots: list[str]) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        path = Path(call.arguments["path"]).resolve()
        if not any(str(path).startswith(str(root)) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")
        return ToolResult(ok=True, output={"path": str(path), "text": path.read_text(encoding="utf-8")})
