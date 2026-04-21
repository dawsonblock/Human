"""Tests for new Stage 2 tools: list_directory, search_files, append_note, write_file_preview."""
from __future__ import annotations

from pathlib import Path

import pytest

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.tools.append_note import AppendNoteTool
from subjective_runtime_v2_1.action.tools.list_directory import ListDirectoryTool
from subjective_runtime_v2_1.action.tools.search_files import SearchFilesTool
from subjective_runtime_v2_1.action.tools.write_file_preview import WriteFilePreviewTool


def _ctx():
    return ExecutionContext(
        run_id="test",
        cycle_id=1,
        idle_tick=False,
        policies={},
        self_model={},
        world_model={},
        regulation={},
    )


# ---- list_directory ----

def test_list_directory_ok(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    (tmp_path / "sub").mkdir()
    tool = ListDirectoryTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="list_directory", arguments={"path": str(tmp_path)}, reason="test", origin="test")
    r = tool.invoke(call, _ctx())
    assert r.ok
    names = [e["name"] for e in r.output["entries"]]
    assert "a.txt" in names
    assert "sub" in names


def test_list_directory_outside_roots(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("other")
    tool = ListDirectoryTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="list_directory", arguments={"path": str(other)}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok
    assert "allowed roots" in r.error


def test_list_directory_nonexistent(tmp_path):
    tool = ListDirectoryTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="list_directory", arguments={"path": str(tmp_path / "nope")}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok


def test_list_directory_on_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    tool = ListDirectoryTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="list_directory", arguments={"path": str(f)}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok


# ---- search_files ----

def test_search_files_finds_match(tmp_path):
    (tmp_path / "notes.txt").write_text("hello world\nfoo bar\n")
    tool = SearchFilesTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="search_files", arguments={"directory": str(tmp_path), "pattern": "hello"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert len(r.output["matches"]) >= 1
    assert r.output["matches"][0]["text"] == "hello world"


def test_search_files_no_match(tmp_path):
    (tmp_path / "notes.txt").write_text("abc\n")
    tool = SearchFilesTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="search_files", arguments={"directory": str(tmp_path), "pattern": "xyz"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert r.output["matches"] == []


def test_search_files_invalid_regex(tmp_path):
    tool = SearchFilesTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="search_files", arguments={"directory": str(tmp_path), "pattern": "["}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok
    assert "invalid pattern" in r.error


def test_search_files_outside_roots(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("other2")
    tool = SearchFilesTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="search_files", arguments={"directory": str(other), "pattern": "x"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok


# ---- append_note ----

def test_append_note_creates_file(tmp_path):
    tool = AppendNoteTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="append_note", arguments={"path": str(tmp_path / "note.md"), "text": "# Title\n"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert (tmp_path / "note.md").read_text() == "# Title\n"


def test_append_note_appends(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("line1\n")
    tool = AppendNoteTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="append_note", arguments={"path": str(f), "text": "line2\n"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert f.read_text() == "line1\nline2\n"


def test_append_note_outside_roots(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("other3")
    tool = AppendNoteTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="append_note", arguments={"path": str(other / "x.txt"), "text": "x"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok


# ---- write_file_preview ----

def test_write_file_preview_does_not_write(tmp_path):
    tool = WriteFilePreviewTool(allowed_roots=[str(tmp_path)])
    target = tmp_path / "out.txt"
    call = ToolCall(tool_name="write_file_preview", arguments={"path": str(target), "text": "proposed"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert not target.exists(), "write_file_preview must NOT write the file"


def test_write_file_preview_returns_artifact(tmp_path):
    tool = WriteFilePreviewTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="write_file_preview", arguments={"path": str(tmp_path / "out.txt"), "text": "new content"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    assert len(r.artifacts) == 1
    art = r.artifacts[0]
    assert art["type"] == "file_write_preview"
    assert art["content"]["proposed_text"] == "new content"
    assert art["content"]["is_new_file"] is True


def test_write_file_preview_captures_existing(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    tool = WriteFilePreviewTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="write_file_preview", arguments={"path": str(f), "text": "new content"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert r.ok
    art = r.artifacts[0]
    assert art["content"]["existing_text"] == "old content"
    assert art["content"]["is_new_file"] is False


def test_write_file_preview_outside_roots(tmp_path, tmp_path_factory):
    other = tmp_path_factory.mktemp("other4")
    tool = WriteFilePreviewTool(allowed_roots=[str(tmp_path)])
    call = ToolCall(tool_name="write_file_preview", arguments={"path": str(other / "x.txt"), "text": "x"}, reason="t", origin="t")
    r = tool.invoke(call, _ctx())
    assert not r.ok


# ---- registry includes new tools ----

def test_registry_contains_new_tools(tmp_path):
    from subjective_runtime_v2_1.action.tools import build_tool_registry
    r = build_tool_registry(allowed_roots=[str(tmp_path)])
    names = {s["name"] for s in r.specs()}
    assert "list_directory" in names
    assert "search_files" in names
    assert "append_note" in names
    assert "write_file_preview" in names
