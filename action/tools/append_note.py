from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_APPEND_BYTES = 100_000  # 100 KB per append


class AppendNoteTool(Tool):
    spec = ToolSpec(
        name="append_note",
        description="append text to a note file inside allowed roots (creates if absent)",
        input_schema={"type": "object", "required": ["path", "text"]},
        side_effect_level="low",
        allowed_in_idle=False,
        reversibility="partial",
        observability="high",
        blast_radius="low",
    )

    def __init__(self, allowed_roots: list[str]) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        path = Path(call.arguments["path"]).resolve()
        text: str = call.arguments["text"]

        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="path outside allowed roots")
        if len(text.encode("utf-8")) > _MAX_APPEND_BYTES:
            return ToolResult(ok=False, output={}, error="append text exceeds 100 KB limit")

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)

        return ToolResult(
            ok=True,
            output={"appended": True, "path": str(path), "bytes": len(text.encode("utf-8"))},
        )
