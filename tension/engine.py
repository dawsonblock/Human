from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, Tension


class TensionEngine:
    def generate(self, state: AgentStateV2_1) -> list[Tension]:
        tensions: list[Tension] = []
        if state.regulation.get("uncertainty_load", 0.0) > 0.6:
            tensions.append(Tension(kind="uncertainty", severity=state.regulation["uncertainty_load"], description="uncertainty is elevated"))
        if state.regulation.get("continuity_health", 1.0) < 0.5:
            tensions.append(Tension(kind="continuity_breakdown", severity=1.0 - state.regulation["continuity_health"], description="continuity is strained"))
        if state.regulation.get("unresolved_loop_burden", 0.0) > 0.4:
            tensions.append(Tension(kind="open_loop_burden", severity=state.regulation["unresolved_loop_burden"], description="too many unresolved loops"))
        if any(c.conflict_type == "evidence" for c in state.conflict_field):
            tensions.append(Tension(kind="evidence_conflict", severity=0.55, description="raw observations conflict with interpreted state"))
        return tensions
