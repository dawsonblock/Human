from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


_HYPOTHESIS_KINDS = ("sensor_error", "world_changed", "bad_model")


class HypothesisEngine:
    """Generate hypotheses to explain active tensions."""

    def generate(self, state: AgentStateV2_1) -> AgentStateV2_1:
        discrepancy_tensions = [t for t in state.tensions if t.kind == "discrepancy"]
        if not discrepancy_tensions:
            return state

        severity = max(t.severity for t in discrepancy_tensions)
        base_conf = min(0.6, 0.2 + severity * 0.4)

        state.hypotheses = [
            {"kind": "sensor_error", "confidence": base_conf * 0.7, "source": "hypothesis_engine"},
            {"kind": "world_changed", "confidence": base_conf * 0.9, "source": "hypothesis_engine"},
            {"kind": "bad_model", "confidence": base_conf * 0.8, "source": "hypothesis_engine"},
        ]
        return state
