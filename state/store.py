from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from subjective_runtime_v2_1.state.models import (
    ActionOption,
    AgentStateV2_1,
    Candidate,
    ConflictItem,
    ContinuityTrace,
    InterpretiveBias,
    NarrativeFrame,
    RawObservation,
    Tension,
    ValenceSignal,
)


def state_to_dict(state: AgentStateV2_1) -> dict[str, Any]:
    return asdict(state)


def _candidate_from_dict(data: dict[str, Any]) -> Candidate:
    return Candidate(**data)


def _tension_from_dict(data: dict[str, Any]) -> Tension:
    return Tension(**data)


def _raw_from_dict(data: dict[str, Any]) -> RawObservation:
    return RawObservation(**data)


def _valence_from_dict(data: dict[str, Any]) -> ValenceSignal:
    return ValenceSignal(**data)


def _conflict_from_dict(data: dict[str, Any]) -> ConflictItem:
    return ConflictItem(**data)


def _continuity_from_dict(data: dict[str, Any]) -> ContinuityTrace:
    return ContinuityTrace(**data)


def _narrative_from_dict(data: dict[str, Any]) -> NarrativeFrame:
    return NarrativeFrame(**data)


def _bias_from_dict(data: dict[str, Any]) -> InterpretiveBias:
    return InterpretiveBias(**data)


def _action_from_dict(data: dict[str, Any]) -> ActionOption:
    return ActionOption(**data)


def state_from_dict(data: dict[str, Any]) -> AgentStateV2_1:
    payload = dict(data)
    payload['raw_observations'] = [_raw_from_dict(x) for x in payload.get('raw_observations', [])]
    payload['active_focus'] = [_candidate_from_dict(x) for x in payload.get('active_focus', [])]
    payload['tensions'] = [_tension_from_dict(x) for x in payload.get('tensions', [])]
    payload['pending_options'] = [_action_from_dict(x) for x in payload.get('pending_options', [])]
    payload['valuation_field'] = [_valence_from_dict(x) for x in payload.get('valuation_field', [])]
    payload['conflict_field'] = [_conflict_from_dict(x) for x in payload.get('conflict_field', [])]
    payload['continuity_field'] = _continuity_from_dict(payload.get('continuity_field', {'summary': ''}))
    payload['pre_narrative'] = _narrative_from_dict(payload.get('pre_narrative', {
        'current_scene': 'idle',
        'self_position': 'stable',
        'main_concern': 'none',
        'active_goal_meaning': 'none',
        'recent_change': 'none',
        'next_expected_turn': 'observe',
        'confidence': 0.0,
    }))
    payload['post_narrative'] = _narrative_from_dict(payload.get('post_narrative', {
        'current_scene': 'idle',
        'self_position': 'stable',
        'main_concern': 'none',
        'active_goal_meaning': 'none',
        'recent_change': 'none',
        'next_expected_turn': 'observe',
        'confidence': 0.0,
    }))
    payload['interpretive_bias'] = _bias_from_dict(payload.get('interpretive_bias', {}))
    payload['workspace'] = [_candidate_from_dict(x) for x in payload.get('workspace', [])]
    return AgentStateV2_1(**payload)


class InMemoryStateStore:
    def __init__(self) -> None:
        self._states: dict[str, AgentStateV2_1] = {}

    def load(self, run_id: str) -> AgentStateV2_1:
        if run_id not in self._states:
            self._states[run_id] = AgentStateV2_1()
        return deepcopy(self._states[run_id])

    def save(self, run_id: str, state: AgentStateV2_1) -> None:
        self._states[run_id] = deepcopy(state)
