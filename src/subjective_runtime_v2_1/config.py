from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeConfig:
    attention_weights: dict[str, float] = field(default_factory=lambda: {
        "salience": 0.18,
        "goal_relevance": 0.16,
        "uncertainty_reduction": 0.10,
        "novelty": 0.08,
        "recency": 0.08,
        "valuation_alignment": 0.14,
        "continuity_match": 0.14,
        "conflict_pressure": 0.12,
        "information_gain": 0.0,
    })
    attention_weights_explore: dict[str, float] = field(default_factory=lambda: {
        "salience": 0.18,
        "goal_relevance": 0.12,
        "uncertainty_reduction": 0.18,
        "novelty": 0.20,
        "recency": 0.08,
        "valuation_alignment": 0.10,
        "continuity_match": 0.08,
        "conflict_pressure": 0.08,
        "information_gain": 0.06,
    })
    attention_weights_exploit: dict[str, float] = field(default_factory=lambda: {
        "salience": 0.20,
        "goal_relevance": 0.22,
        "uncertainty_reduction": 0.12,
        "novelty": 0.04,
        "recency": 0.08,
        "valuation_alignment": 0.12,
        "continuity_match": 0.14,
        "conflict_pressure": 0.10,
        "information_gain": 0.06,
    })
    action_weights: dict[str, float] = field(default_factory=lambda: {
        "expected_value": 0.22,
        "estimated_cost": -0.14,
        "estimated_risk": -0.14,
        "tension_reduction": 0.12,
        "uncertainty_reduction": 0.12,
        "continuity_preservation": 0.10,
        "valuation_alignment": 0.08,
        "narrative_fit": 0.04,
        "conflict_resolution_value": 0.04,
        "information_gain": 0.10,
        "mode_fit": 0.08,
    })
    mode_switch: dict[str, float] = field(default_factory=lambda: {
        "explore_min_continuity": 0.8,
        "explore_max_burden": 0.3,
        "exploit_overload": 0.7,
        "exploit_error": 0.6,
    })
    thought_budget: dict[str, int] = field(default_factory=lambda: {
        "base": 1,
        "high_error": 3,
        "high_uncertainty": 2,
        "max": 4,
    })
    associative_limits: dict[str, float] = field(default_factory=lambda: {
        "max_pairs": 3,
        "max_outputs": 2,
        "min_novelty_gap": 0.15,
    })
    conflict_age_limit: int = 12
