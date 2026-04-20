from subjective_runtime_v2_1.engines.narrative import NarrativeEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Tension


def test_narrative_changes_with_goal_and_outcome():
    engine = NarrativeEngine()
    state = AgentStateV2_1()
    n1 = engine.build_pre(state)
    state.goal_stack = [{"name": "alpha"}]
    state.tensions = [Tension(kind="uncertainty", severity=0.8, description="x")]
    state.last_outcome = {"status": "error"}
    n2 = engine.build_pre(state)
    assert n1.current_scene != n2.current_scene
    assert n2.main_concern == "uncertainty"
