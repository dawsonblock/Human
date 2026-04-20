from __future__ import annotations

import warnings


def build_tool_registry(allowed_roots: list[str], memory_sink: list[dict] | None = None):
    """Build and return the default tool registry.

    ``memory_sink`` is deprecated and ignored; memory writes now produce state
    mutations via ``ToolResult.memory_writes`` and are applied by RuntimeCore.
    Passing a non-None value emits a DeprecationWarning.
    """
    if memory_sink is not None:
        warnings.warn(
            "build_tool_registry(memory_sink=...) is deprecated and has no effect. "
            "Memory writes are handled via ToolResult.memory_writes.",
            DeprecationWarning,
            stacklevel=2,
        )
    from subjective_runtime_v2_1.action.registry import ToolRegistry
    from subjective_runtime_v2_1.action.tools.echo import EchoTool
    from subjective_runtime_v2_1.action.tools.file_read import FileReadTool
    from subjective_runtime_v2_1.action.tools.file_write import FileWriteTool
    from subjective_runtime_v2_1.action.tools.http_get import HttpGetTool
    from subjective_runtime_v2_1.action.tools.memory_write import MemoryWriteTool

    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(MemoryWriteTool())
    registry.register(FileReadTool(allowed_roots=allowed_roots))
    registry.register(FileWriteTool(allowed_roots=allowed_roots))
    registry.register(HttpGetTool())
    return registry
