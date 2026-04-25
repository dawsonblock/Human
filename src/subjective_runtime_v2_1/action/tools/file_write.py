from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_WRITE_BYTES = 1_000_000  # 1 MB


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
        try:
            path = Path(call.arguments["path"]).resolve()
        except (TypeError, ValueError) as e:
            return ToolResult(ok=False, output={}, error=f"invalid path argument: {e}")

        text = call.arguments.get("text", "")
        if not isinstance(text, str):
            return ToolResult(ok=False, output={}, error="text argument must be a string")

        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")

        encoded = text.encode("utf-8")
        if len(encoded) > _MAX_WRITE_BYTES:
            return ToolResult(
                ok=False,
                output={},
                error=f"write content too large ({len(encoded)} bytes > {_MAX_WRITE_BYTES} byte limit)",
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            return ToolResult(ok=False, output={}, error=f"cannot write file: {e}")

        return ToolResult(ok=True, output={"written": True, "path": str(path), "bytes": len(encoded)})
