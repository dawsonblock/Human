from subjective_runtime_v2_1.engines.continuity import ContinuityEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_continuity_preserves_themes_actions_failures():
    state = AgentStateV2_1()
    state.goal_stack = [{"name": "alpha"}]
    state.last_action = {"name": "step1"}
    state.last_outcome = {"status": "error"}
    trace = ContinuityEngine().update(state)
    assert "alpha" in trace.active_themes
    assert trace.recent_events[-1]["action"]["name"] == "step1"
    assert trace.open_loops
    assert trace.recency_weight > 0.0
    assert trace.momentum_weight > 0.0
