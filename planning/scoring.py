from __future__ import annotations

from subjective_runtime_v2_1.config import RuntimeConfig
from subjective_runtime_v2_1.state.models import ActionOption, AgentStateV2_1


def score_action(action: ActionOption, config: RuntimeConfig | None = None, state: AgentStateV2_1 | None = None) -> float:
    cfg = (config or RuntimeConfig()).action_weights
    mode_fit = action.mode_fit
    if state is not None and mode_fit == 0.0:
        if state.cognitive_mode == "EXPLORE":
            mode_fit = min(1.0, 0.5 * action.information_gain + 0.3 * action.expected_value + 0.2 * state.risk_appetite)
        else:
            mode_fit = min(1.0, 0.5 * action.continuity_preservation + 0.3 * action.expected_value + 0.2 * (1.0 - action.estimated_risk))
    return (
        cfg["expected_value"] * action.expected_value +
        cfg["estimated_cost"] * action.estimated_cost +
        cfg["estimated_risk"] * action.estimated_risk +
        cfg["tension_reduction"] * action.tension_reduction +
        cfg["uncertainty_reduction"] * action.uncertainty_reduction +
        cfg["continuity_preservation"] * action.continuity_preservation +
        cfg["valuation_alignment"] * action.valuation_alignment +
        cfg["narrative_fit"] * action.narrative_fit +
        cfg["conflict_resolution_value"] * action.conflict_resolution_value +
        cfg["information_gain"] * action.information_gain +
        cfg["mode_fit"] * mode_fit
    )
