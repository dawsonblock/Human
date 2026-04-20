from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.state.models import AgentStateV2_1, ActionOption


def test_file_write_requires_approval():
    registry = build_tool_registry(memory_sink=[], allowed_roots=["."])
    gate = ActionGate(registry)
    state = AgentStateV2_1()
    action = ActionOption(
        id="a1", name="write",
        target={"tool_name": "file_write", "arguments": {"path": "./x.txt", "text": "x"}},
        predicted_world_effect={}, predicted_self_effect={},
        expected_value=0.1, estimated_cost=0.1, estimated_risk=0.1
    )
    approved, reason = gate.approve(state, action, idle_tick=False)
    assert approved is False
    assert reason == "approval_required"
