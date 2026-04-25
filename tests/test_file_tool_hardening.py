"""Tests for hardened file tool error handling."""
from __future__ import annotations

import pytest

from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.tools.file_read import FileReadTool
from subjective_runtime_v2_1.action.tools.file_write import FileWriteTool
from subjective_runtime_v2_1.action.tools.append_note import AppendNoteTool


def _ctx():
    from subjective_runtime_v2_1.action.context import ExecutionContext
    return ExecutionContext(
        run_id="test",
        cycle_id=0,
        idle_tick=False,
        policies={},
        self_model={},
        world_model={},
        regulation={},
    )


def _call(tool_name: str, **kwargs) -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments=kwargs, reason="test", origin="test")


# ── FileReadTool ─────────────────────────────────────────────────────────────

class TestFileRead:
    def setup_method(self):
        self.tmp = None

    def test_outside_root_rejected(self, tmp_path):
        tool = FileReadTool(allowed_roots=[str(tmp_path / "allowed")])
        result = tool.invoke(_call("file_read", path=str(tmp_path / "secret.txt")), _ctx())
        assert not result.ok
        assert "outside allowed roots" in result.error

    def test_missing_file_returns_error(self, tmp_path):
        tool = FileReadTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(_call("file_read", path=str(tmp_path / "nope.txt")), _ctx())
        assert not result.ok
        assert "does not exist" in result.error

    def test_directory_as_file_returns_error(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        tool = FileReadTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(_call("file_read", path=str(subdir)), _ctx())
        assert not result.ok
        assert "not a regular file" in result.error

    def test_large_file_rejected(self, tmp_path):
        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * (1_000_001))
        tool = FileReadTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(_call("file_read", path=str(big)), _ctx())
        assert not result.ok
        assert "too large" in result.error

    def test_normal_file_read_succeeds(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        tool = FileReadTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(_call("file_read", path=str(f)), _ctx())
        assert result.ok
        assert result.output["text"] == "hello world"

    def test_binary_ish_content_does_not_crash(self, tmp_path):
        """Binary files should come back as replacement-char strings, not exceptions."""
        f = tmp_path / "bin.dat"
        f.write_bytes(bytes(range(256)))
        tool = FileReadTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(_call("file_read", path=str(f)), _ctx())
        # ok=True with errors='replace' — no exception
        assert result.ok


# ── FileWriteTool ────────────────────────────────────────────────────────────

class TestFileWrite:
    def test_outside_root_rejected(self, tmp_path):
        tool = FileWriteTool(allowed_roots=[str(tmp_path / "allowed")])
        result = tool.invoke(_call("file_write", path=str(tmp_path / "bad.txt"), text="x"), _ctx())
        assert not result.ok
        assert "outside allowed roots" in result.error

    def test_write_too_large_rejected(self, tmp_path):
        tool = FileWriteTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(
            _call("file_write", path=str(tmp_path / "big.txt"), text="x" * 1_000_001),
            _ctx(),
        )
        assert not result.ok
        assert "too large" in result.error

    def test_normal_write_succeeds(self, tmp_path):
        tool = FileWriteTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(
            _call("file_write", path=str(tmp_path / "out.txt"), text="hello"),
            _ctx(),
        )
        assert result.ok
        assert (tmp_path / "out.txt").read_text() == "hello"


# ── AppendNoteTool ────────────────────────────────────────────────────────────

class TestAppendNote:
    def test_outside_root_rejected(self, tmp_path):
        tool = AppendNoteTool(allowed_roots=[str(tmp_path / "allowed")])
        result = tool.invoke(_call("append_note", path=str(tmp_path / "note.md"), text="hi"), _ctx())
        assert not result.ok
        assert "outside allowed roots" in result.error

    def test_too_large_rejected(self, tmp_path):
        tool = AppendNoteTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(
            _call("append_note", path=str(tmp_path / "note.md"), text="x" * 100_001),
            _ctx(),
        )
        assert not result.ok
        assert "100 KB" in result.error

    def test_normal_append_succeeds(self, tmp_path):
        tool = AppendNoteTool(allowed_roots=[str(tmp_path)])
        result = tool.invoke(
            _call("append_note", path=str(tmp_path / "note.md"), text="line1\n"),
            _ctx(),
        )
        assert result.ok
        assert (tmp_path / "note.md").read_text() == "line1\n"
