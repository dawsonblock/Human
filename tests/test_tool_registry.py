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


def test_specs_returns_serializable_dicts():
    """Regression: ToolSpec is a slotted dataclass — __dict__ raises AttributeError.
    specs() must use dataclasses.asdict() instead."""
    registry = build_tool_registry(allowed_roots=["."])
    specs = registry.specs()
    assert isinstance(specs, list)
    assert len(specs) > 0
    for spec in specs:
        assert isinstance(spec, dict), f"spec is not a dict: {spec!r}"
        assert "name" in spec
        assert "description" in spec


def test_http_get_not_in_registry():
    """http_get is a non-functional stub; it must not be registered."""
    registry = build_tool_registry(allowed_roots=["."])
    names = [s["name"] for s in registry.specs()]
    assert "http_get" not in names
