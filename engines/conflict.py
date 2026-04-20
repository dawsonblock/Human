from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, ConflictItem


class ConflictEngine:
    def update(self, state: AgentStateV2_1) -> list[ConflictItem]:
        existing: dict[str, ConflictItem] = {}
        for c in state.conflict_field:
            if not c.resolved:
                c.age_cycles += 1
                existing[c.id] = c

        if state.goal_stack and state.regulation.get("uncertainty_load", 0.0) > 0.55:
            cid = "priority_goal_vs_probe"
            existing.setdefault(cid, ConflictItem(
                id=cid,
                domain="planning",
                conflict_type="priority",
                option_a={"name": "continue_goal"},
                option_b={"name": "probe_uncertainty"},
                tension=0.7,
                preferred_resolution_mode="deliberate",
            ))

        if state.regulation.get("continuity_health", 1.0) < 0.45 and state.regulation.get("overload_pressure", 0.0) > 0.4:
            cid = "policy_act_vs_recover"
            existing.setdefault(cid, ConflictItem(
                id=cid,
                domain="safety",
                conflict_type="policy",
                option_a={"name": "continue_operating"},
                option_b={"name": "recover_and_slow"},
                tension=0.8,
                preferred_resolution_mode="stabilize",
            ))

        if state.raw_observations and state.interpreted_percepts.get("status") == "stable":
            last_obs = state.raw_observations[-1]
            observed = last_obs.payload.get("observed_status")
            if observed and observed != "stable":
                cid = "evidence_status_mismatch"
                existing.setdefault(cid, ConflictItem(
                    id=cid,
                    domain="world_model",
                    conflict_type="evidence",
                    option_a={"name": "trust_interpreted"},
                    option_b={"name": "trust_observation"},
                    tension=0.65,
                    preferred_resolution_mode="verify",
                ))

        return list(existing.values())
