from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, InterpretiveBias


class InterpretiveBiasEngine:
    """Derive interpretive bias from continuity field and valuation signals."""

    def derive(self, state: AgentStateV2_1) -> InterpretiveBias:
        prioritized_themes = list(state.continuity_field.active_themes[:4])

        threat_bias = 0.0
        for signal in state.valuation_field:
            if signal.kind in ("threatening", "costly"):
                threat_bias = min(1.0, threat_bias + signal.magnitude * 0.4)

        novelty_bias = min(0.8, state.regulation.get("uncertainty_load", 0.2) * 0.6)
        continuity_bias = state.regulation.get("continuity_health", 0.8) * 0.5
        social_bias = min(0.6, len(state.social_model) * 0.1)

        risk_appetite = state.risk_appetite
        mode = state.cognitive_mode

        return InterpretiveBias(
            prioritized_themes=prioritized_themes,
            threat_bias=threat_bias,
            novelty_bias=novelty_bias,
            continuity_bias=continuity_bias,
            social_bias=social_bias,
            risk_appetite=risk_appetite,
            mode=mode,
        )
