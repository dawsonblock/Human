from subjective_runtime_v2_1.engines.consequence import ConsequenceEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_failure_updates_error_and_confidence():
    state = AgentStateV2_1()
    state.last_action = {"name": "demo"}
    state.last_outcome = {"status": "error"}
    out = ConsequenceEngine().apply(state)
    assert out.regulation["error_accumulation"] > 0.0
    assert out.self_model["confidence_profile"]["demo"] < 0.5


def test_success_improves_confidence_and_continuity():
    state = AgentStateV2_1()
    state.last_action = {"name": "demo"}
    state.last_outcome = {"status": "ok"}
    out = ConsequenceEngine().apply(state)
    assert out.self_model["confidence_profile"]["demo"] > 0.5
    assert out.regulation["continuity_health"] > 0.8
