from subjective_runtime_v2_1.engines.homeostasis import HomeostasisEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_homeostasis_raises_overload_and_lowers_risk_appetite():
    state = AgentStateV2_1()
    state.regulation["error_accumulation"] = 0.8
    state.regulation["unresolved_loop_burden"] = 0.7
    updated = HomeostasisEngine().update(state)
    assert updated.regulation["overload_pressure"] > 0.4
    assert updated.risk_appetite < 0.4
