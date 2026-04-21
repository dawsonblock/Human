"""Regression tests for DiscrepancyModule.

The module must compare raw observed status against world_model['expected_status'],
not against interpreted_percepts['status'].  The old code compared against the
interpreted percept that was written from the same input in the same cycle —
making the branch permanently unreachable.
"""
from __future__ import annotations

from subjective_runtime_v2_1.modules.discrepancy import DiscrepancyModule
from subjective_runtime_v2_1.state.models import AgentStateV2_1, InterpretiveBias, RawObservation


def _bias() -> InterpretiveBias:
    return InterpretiveBias()


def test_discrepancy_fires_when_observed_differs_from_world_model():
    module = DiscrepancyModule()
    state = AgentStateV2_1()
    # World model holds the expected status set by a prior tool action.
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
    # Set interpreted_percepts to the same value as observed — in the old code
    # this would have suppressed the discrepancy because both sides matched.
    state.interpreted_percepts["status"] = "degraded"

    candidates = module.run(state, {}, _bias())
    assert len(candidates) == 1
    assert candidates[0].kind == "status_mismatch"
    assert candidates[0].content["observed"] == "degraded"
    assert candidates[0].content["expected"] == "stable"


def test_discrepancy_silent_when_consistent_with_world_model():
    module = DiscrepancyModule()
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
    candidates = module.run(state, {}, _bias())
    assert candidates == []


def test_discrepancy_silent_when_no_world_model_expectation():
    module = DiscrepancyModule()
    state = AgentStateV2_1()
    # No expected_status in world_model — nothing to compare against.
    state.raw_observations.append(
        RawObservation(
            source="sensor",
            modality="text",
            payload={"observed_status": "degraded"},
            confidence=1.0,
            timestamp=0.0,
        )
    )
    candidates = module.run(state, {}, _bias())
    assert candidates == []
