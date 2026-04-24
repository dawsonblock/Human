from __future__ import annotations

from abc import ABC, abstractmethod

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec


class Tool(ABC):
    spec: ToolSpec

    @abstractmethod
    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        raise NotImplementedError
