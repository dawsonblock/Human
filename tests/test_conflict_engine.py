from subjective_runtime_v2_1.engines.conflict import ConflictEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1, RawObservation


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


def test_evidence_status_mismatch_triggers_on_world_model():
    """Regression: evidence_status_mismatch must compare raw observation against
    world_model['expected_status'], not interpreted_percepts['status'].

    The old code compared against interpreted_percepts which is always updated
    from the same input in the same cycle — making the branch unreachable."""
    engine = ConflictEngine()
    state = AgentStateV2_1()
    # World model says stable; raw observation says degraded.
    state.world_model["expected_status"] = "stable"
    state.raw_observations.append(
        RawObservation(
            source="sensor",
            modality="text",
            payload={"observed_status": "degraded"},
            confidence=1.0,
            timestamp=0.0,
        )
    )
    conflicts = engine.update(state)
    ids = [c.id for c in conflicts]
    assert "evidence_status_mismatch" in ids


def test_evidence_status_mismatch_absent_when_consistent():
    """No mismatch conflict when observed status matches world-model expectation."""
    engine = ConflictEngine()
    state = AgentStateV2_1()
    state.world_model["expected_status"] = "stable"
    state.raw_observations.append(
        RawObservation(
            source="sensor",
            modality="text",
            payload={"observed_status": "stable"},
            confidence=1.0,
            timestamp=0.0,
        )
    )
    conflicts = engine.update(state)
    ids = [c.id for c in conflicts]
    assert "evidence_status_mismatch" not in ids
