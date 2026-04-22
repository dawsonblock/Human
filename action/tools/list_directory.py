from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_ENTRIES = 500


class ListDirectoryTool(Tool):
    spec = ToolSpec(
        name="list_directory",
        description="list files and subdirectories in a directory within allowed roots",
        input_schema={"type": "object", "required": ["path"]},
        side_effect_level="none",
        allowed_in_idle=True,
        reversibility="full",
        observability="high",
        blast_radius="low",
    )

    def __init__(self, allowed_roots: list[str]) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        path = Path(call.arguments["path"]).resolve()
        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")
        if not path.exists():
            return ToolResult(ok=False, output={}, error=f"path does not exist: {path}")
        if not path.is_dir():
            return ToolResult(ok=False, output={}, error=f"path is not a directory: {path}")
        entries = []
        count = 0
        for child in sorted(path.iterdir()):
            if count >= _MAX_ENTRIES:
                break
            entries.append({
                "name": child.name,
                "path": str(child),
                "is_dir": child.is_dir(),
                "size": child.stat().st_size if child.is_file() else None,
            })
            count += 1
        return ToolResult(
            ok=True,
            output={
                "path": str(path),
                "entries": entries,
                "truncated": count >= _MAX_ENTRIES,
            },
        )
