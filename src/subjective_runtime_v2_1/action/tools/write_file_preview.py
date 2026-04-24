from __future__ import annotations

from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_PREVIEW_BYTES = 500_000  # 500 KB


class WriteFilePreviewTool(Tool):
    """Stage a file write for operator approval.

    This tool does NOT write the file.  It validates the target path, captures
    the proposed content, and returns an artifact dict that the runtime records
    as a ``file_write_preview`` artifact.  The operator approves via the
    approval flow; the actual write is then performed by ``file_write``.
    """

    spec = ToolSpec(
        name="write_file_preview",
        description=(
            "stage a file write for operator approval; "
            "returns a preview artifact — does NOT write the file"
        ),
        input_schema={"type": "object", "required": ["path", "text"]},
        side_effect_level="none",
        requires_confirmation=False,
        allowed_in_idle=False,
        reversibility="full",
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
        if len(text.encode("utf-8")) > _MAX_PREVIEW_BYTES:
            return ToolResult(ok=False, output={}, error="preview text exceeds 500 KB limit")

        existing_text: str | None = None
        if path.exists():
            try:
                existing_text = path.read_text(encoding="utf-8")
            except OSError:
                existing_text = None

        preview_artifact = {
            "type": "file_write_preview",
            "title": f"Write preview: {path.name}",
            "content": {
                "path": str(path),
                "proposed_text": text,
                "existing_text": existing_text,
                "is_new_file": not path.exists(),
            },
        }

        return ToolResult(
            ok=True,
            output={"previewed": True, "path": str(path)},
            artifacts=[preview_artifact],
        )
