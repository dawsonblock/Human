from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.tools import build_tool_registry


def test_tool_registry_dispatch():
    registry = build_tool_registry(allowed_roots=["."])
    result = registry.invoke(
        ToolCall(tool_name="echo", arguments={"message": "hi"}, reason="test"),
        ExecutionContext("r", 1, False, {}, {}, {}, {}),
    )
    assert result.ok is True
    assert result.output["message"] == "hi"
