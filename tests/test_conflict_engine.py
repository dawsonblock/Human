from subjective_runtime_v2_1.engines.conflict import ConflictEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_conflict_persists_and_ages():
    engine = ConflictEngine()
    state = AgentStateV2_1()
    state.goal_stack = [{"name": "alpha"}]
    state.regulation["uncertainty_load"] = 0.8
    first = engine.update(state)
    state.conflict_field = first
    second = engine.update(state)
    assert second
    assert second[0].age_cycles >= 1
