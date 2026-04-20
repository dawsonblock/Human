from subjective_runtime_v2_1.modules.associative import AssociativeModule
from subjective_runtime_v2_1.state.models import AgentStateV2_1, InterpretiveBias


def test_associative_module_only_runs_in_explore():
    m = AssociativeModule()
    state = AgentStateV2_1()
    state.working_memory = [{"kind": "tension"}, {"kind": "episodic_memory"}]
    state.cognitive_mode = "EXPLOIT"
    assert m.run(state, {}, InterpretiveBias()) == []
    state.cognitive_mode = "EXPLORE"
    out = m.run(state, {}, InterpretiveBias())
    assert len(out) == 1
    assert out[0].kind == "associative_bridge"
