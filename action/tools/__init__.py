from __future__ import annotations


def build_tool_registry(memory_sink: list[dict], allowed_roots: list[str]):
    from subjective_runtime_v2_1.action.registry import ToolRegistry
    from subjective_runtime_v2_1.action.tools.echo import EchoTool
    from subjective_runtime_v2_1.action.tools.file_read import FileReadTool
    from subjective_runtime_v2_1.action.tools.file_write import FileWriteTool
    from subjective_runtime_v2_1.action.tools.http_get import HttpGetTool
    from subjective_runtime_v2_1.action.tools.memory_write import MemoryWriteTool

    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(MemoryWriteTool(memory_sink))
    registry.register(FileReadTool(allowed_roots=allowed_roots))
    registry.register(FileWriteTool(allowed_roots=allowed_roots))
    registry.register(HttpGetTool())
    return registry
