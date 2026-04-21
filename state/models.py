from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawObservation:
    source: str
    modality: str
    payload: dict[str, Any]
    confidence: float
    timestamp: float
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Candidate:
    id: str
    source: str
    kind: str
    content: dict[str, Any]
    confidence: float
    salience: float
    goal_relevance: float
    uncertainty_reduction: float = 0.0
    novelty: float = 0.0
    recency: float = 1.0
    valuation_alignment: float = 0.0
    continuity_match: float = 0.0
    conflict_pressure: float = 0.0
    information_gain: float = 0.0


@dataclass(slots=True)
class Tension:
    kind: str
    severity: float
    description: str
    source: str = "runtime"


@dataclass(slots=True)
class ValenceSignal:
    target: str
    kind: str
    magnitude: float
    source: str
    timestamp: float
    decay_class: str = "medium"
    causal_targets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConflictItem:
    id: str
    domain: str
    conflict_type: str
    option_a: dict[str, Any]
    option_b: dict[str, Any]
    tension: float
    age_cycles: int = 0
    resolved: bool = False
    preferred_resolution_mode: str = "deliberate"


@dataclass(slots=True)
class ContinuityTrace:
    summary: str
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    active_themes: list[str] = field(default_factory=list)
    open_loops: list[dict[str, Any]] = field(default_factory=list)
    recency_weight: float = 0.5
    momentum_weight: float = 0.5


@dataclass(slots=True)
class NarrativeFrame:
    current_scene: str
    self_position: str
    main_concern: str
    active_goal_meaning: str
    recent_change: str
    next_expected_turn: str
    confidence: float


@dataclass(slots=True)
class InterpretiveBias:
    prioritized_themes: list[str] = field(default_factory=list)
    threat_bias: float = 0.0
    novelty_bias: float = 0.0
    continuity_bias: float = 0.0
    social_bias: float = 0.0
    risk_appetite: float = 0.0
    mode: str = "EXPLOIT"


@dataclass(slots=True)
class PlanStep:
    id: str
    description: str
    tool_name: str
    arguments: dict[str, Any]
    status: str = "pending"  # pending/running/completed/failed/skipped
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Plan:
    id: str
    goal_id: str
    steps: list[PlanStep]
    assumptions: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    current_step: int = 0
    status: str = "active"  # active/completed/failed/blocked/cancelled
    created_at: float = 0.0
    replans: int = 0


@dataclass(slots=True)
class Goal:
    id: str
    type: str
    description: str
    priority: float = 0.5
    success_criteria: str = ""
    status: str = "active"  # active/completed/failed/abandoned
    created_at: float = 0.0


@dataclass(slots=True)
class Artifact:
    id: str
    run_id: str
    type: str  # summary/extracted_facts/draft_note/file_write_preview/tool_output/final_report
    title: str
    content: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    step_id: str | None = None


@dataclass(slots=True)
class ActionOption:
    id: str
    name: str
    target: dict[str, Any]
    predicted_world_effect: dict[str, Any]
    predicted_self_effect: dict[str, Any]
    expected_value: float
    estimated_cost: float
    estimated_risk: float
    tension_reduction: float = 0.0
    uncertainty_reduction: float = 0.0
    continuity_preservation: float = 0.0
    valuation_alignment: float = 0.0
    narrative_fit: float = 0.0
    conflict_resolution_value: float = 0.0
    information_gain: float = 0.0
    mode_fit: float = 0.0


@dataclass(slots=True)
class AgentStateV2_1:
    timestamp: float = 0.0
    cycle_id: int = 0

    raw_observations: list[RawObservation] = field(default_factory=list)
    interpreted_percepts: dict[str, Any] = field(default_factory=dict)
    world_model: dict[str, Any] = field(default_factory=dict)
    self_model: dict[str, Any] = field(default_factory=lambda: {
        "identity": {"role": "runtime"},
        "commitments": [],
        "capabilities": {},
        "limits": {"blocked_tools": []},
        "confidence_profile": {},
        "domain_fragility": {},
        "recent_failures": [],
    })

    active_focus: list[Candidate] = field(default_factory=list)
    goal_stack: list[dict[str, Any]] = field(default_factory=list)
    tensions: list[Tension] = field(default_factory=list)
    pending_options: list[ActionOption] = field(default_factory=list)

    cognitive_mode: str = "EXPLOIT"
    risk_appetite: float = 0.2
    thought_budget: int = 1
    hypotheses: list[dict[str, Any]] = field(default_factory=list)

    regulation: dict[str, float] = field(default_factory=lambda: {
        "uncertainty_load": 0.2,
        "continuity_health": 0.8,
        "error_accumulation": 0.0,
        "overload_pressure": 0.0,
        "recovery_debt": 0.0,
        "novelty_saturation": 0.0,
        "unresolved_loop_burden": 0.0,
        "memory_pressure": 0.1,
        "goal_drift": 0.1,
    })

    working_memory: list[dict[str, Any]] = field(default_factory=list)
    episodic_trace: list[dict[str, Any]] = field(default_factory=list)
    self_history: list[dict[str, Any]] = field(default_factory=list)

    valuation_field: list[ValenceSignal] = field(default_factory=list)
    conflict_field: list[ConflictItem] = field(default_factory=list)
    continuity_field: ContinuityTrace = field(default_factory=lambda: ContinuityTrace(summary=""))
    pre_narrative: NarrativeFrame = field(default_factory=lambda: NarrativeFrame(
        current_scene="idle",
        self_position="stable",
        main_concern="none",
        active_goal_meaning="none",
        recent_change="none",
        next_expected_turn="observe",
        confidence=0.0,
    ))
    post_narrative: NarrativeFrame = field(default_factory=lambda: NarrativeFrame(
        current_scene="idle",
        self_position="stable",
        main_concern="none",
        active_goal_meaning="none",
        recent_change="none",
        next_expected_turn="observe",
        confidence=0.0,
    ))
    social_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    interpretive_bias: InterpretiveBias = field(default_factory=InterpretiveBias)

    workspace: list[Candidate] = field(default_factory=list)
    approval_requests: list[dict[str, Any]] = field(default_factory=list)
    last_consolidation: dict[str, Any] = field(default_factory=dict)

    last_action: dict[str, Any] | None = None
    last_outcome: dict[str, Any] | None = None

    # Stage 2: goal/plan/artifact/observability fields
    active_goal: Goal | None = None
    active_plan: Plan | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    stop_reason: str | None = None  # completed/blocked/awaiting_approval/awaiting_input/error/cancelled
    run_outcome: dict[str, Any] = field(default_factory=dict)
    total_actions: int = 0
    total_replans: int = 0
    last_meaningful_action_ts: float | None = None
