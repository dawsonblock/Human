from subjective_runtime_v2_1.engines.hypothesis import HypothesisEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Tension


def test_hypothesis_engine_generates_bounded_hypotheses():
    state = AgentStateV2_1()
    state.tensions = [Tension(kind="discrepancy", severity=0.7, description="mismatch")]
    state = HypothesisEngine().generate(state)
    assert 1 <= len(state.hypotheses) <= 3
    assert {h["kind"] for h in state.hypotheses} == {"sensor_error", "world_changed", "bad_model"}
