from __future__ import annotations

import re
from pathlib import Path

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

_MAX_MATCHES = 100
_MAX_FILE_BYTES = 1_000_000  # 1 MB per file


class SearchFilesTool(Tool):
    spec = ToolSpec(
        name="search_files",
        description=(
            "search for a pattern across text files in a directory within allowed roots; "
            "returns up to 100 matching lines with file path and line number"
        ),
        input_schema={"type": "object", "required": ["directory", "pattern"]},
        side_effect_level="none",
        allowed_in_idle=True,
        reversibility="full",
        observability="high",
        blast_radius="low",
    )

    def __init__(self, allowed_roots: list[str]) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        directory = Path(call.arguments["directory"]).resolve()
        pattern_str = call.arguments["pattern"]
        glob = call.arguments.get("glob", "**/*")

        if not any(directory.is_relative_to(root) for root in self.allowed_roots):
            return ToolResult(ok=False, output={}, error="directory outside allowed roots")
        if not directory.is_dir():
            return ToolResult(ok=False, output={}, error=f"not a directory: {directory}")

        try:
            regex = re.compile(pattern_str)
        except re.error as exc:
            return ToolResult(ok=False, output={}, error=f"invalid pattern: {exc}")

        matches = []
        files_searched = 0
        for filepath in sorted(directory.glob(glob)):
            if not filepath.is_file():
                continue
            if filepath.stat().st_size > _MAX_FILE_BYTES:
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_searched += 1
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append({
                        "file": str(filepath),
                        "line": lineno,
                        "text": line[:300],
                    })
                    if len(matches) >= _MAX_MATCHES:
                        return ToolResult(
                            ok=True,
                            output={
                                "matches": matches,
                                "files_searched": files_searched,
                                "truncated": True,
                            },
                        )

        return ToolResult(
            ok=True,
            output={
                "matches": matches,
                "files_searched": files_searched,
                "truncated": False,
            },
        )
