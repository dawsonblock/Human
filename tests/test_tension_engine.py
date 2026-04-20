from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.tension.engine import TensionEngine


def test_tensions_generated_from_regulation():
    state = AgentStateV2_1()
    state.regulation["uncertainty_load"] = 0.8
    state.regulation["continuity_health"] = 0.3
    tensions = TensionEngine().generate(state)
    kinds = {t.kind for t in tensions}
    assert "uncertainty" in kinds
    assert "continuity_breakdown" in kinds
