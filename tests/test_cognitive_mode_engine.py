from subjective_runtime_v2_1.engines.cognitive_mode import CognitiveModeEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_mode_engine_explore_and_exploit():
    state = AgentStateV2_1()
    state.regulation["continuity_health"] = 0.9
    state.regulation["unresolved_loop_burden"] = 0.1
    state.regulation["overload_pressure"] = 0.1
    state = CognitiveModeEngine().update(state)
    assert state.cognitive_mode == "EXPLORE"

    state.regulation["overload_pressure"] = 0.8
    state = CognitiveModeEngine().update(state)
    assert state.cognitive_mode == "EXPLOIT"
