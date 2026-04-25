from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_READ_BYTES = 1_000_000  # 1 MB


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
        try:
            path = Path(call.arguments["path"]).resolve()
        except (TypeError, ValueError) as e:
            return ToolResult(ok=False, output={}, error=f"invalid path argument: {e}")

        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")

        if not path.exists():
            return ToolResult(ok=False, output={}, error=f"path does not exist: {path}")

        if not path.is_file():
            return ToolResult(ok=False, output={}, error=f"path is not a regular file: {path}")

        try:
            size = path.stat().st_size
        except OSError as e:
            return ToolResult(ok=False, output={}, error=f"cannot stat file: {e}")

        if size > _MAX_READ_BYTES:
            return ToolResult(
                ok=False,
                output={},
                error=f"file too large ({size} bytes > {_MAX_READ_BYTES} byte limit)",
            )

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult(ok=False, output={}, error=f"cannot read file: {e}")

        return ToolResult(ok=True, output={"path": str(path), "text": text})
