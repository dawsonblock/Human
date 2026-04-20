from dataclasses import asdict

from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_state_roundtrip_shape():
    state = AgentStateV2_1()
    data = asdict(state)
    assert "raw_observations" in data
    assert "valuation_field" in data
    assert "continuity_field" in data
    assert data["pre_narrative"]["current_scene"] == "idle"
