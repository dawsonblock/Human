from subjective_runtime_v2_1.engines.interpretive_bias import InterpretiveBiasEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1, ValenceSignal


def test_bias_changes_under_different_field_state():
    engine = InterpretiveBiasEngine()

    s1 = AgentStateV2_1()
    s1.continuity_field.active_themes = ["alpha"]
    b1 = engine.derive(s1)

    s2 = AgentStateV2_1()
    s2.continuity_field.active_themes = ["beta"]
    s2.valuation_field = [ValenceSignal("beta", "threatening", 0.8, "test", 0.0)]
    b2 = engine.derive(s2)

    assert b1.prioritized_themes != b2.prioritized_themes or b1.threat_bias != b2.threat_bias
