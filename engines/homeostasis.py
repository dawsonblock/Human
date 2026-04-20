from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class HomeostasisEngine:
    def update(self, state: AgentStateV2_1) -> AgentStateV2_1:
        r = state.regulation
        overload = min(
            1.0,
            0.35 * r.get("error_accumulation", 0.0)
            + 0.30 * r.get("unresolved_loop_burden", 0.0)
            + 0.20 * r.get("uncertainty_load", 0.0)
            + 0.15 * r.get("memory_pressure", 0.0),
        )
        r["overload_pressure"] = overload
        r["recovery_debt"] = min(1.0, r.get("recovery_debt", 0.0) * 0.9 + overload * 0.3)
        continuity = r.get("continuity_health", 1.0)
        state.risk_appetite = max(0.05, min(0.95, 0.55 * continuity - 0.45 * overload + 0.15))
        return state
