from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class ConsequenceEngine:
    """Update regulation and self-model confidence based on last action outcome."""

    def apply(self, state: AgentStateV2_1) -> AgentStateV2_1:
        outcome = state.last_outcome
        action = state.last_action
        if not outcome or not action:
            return state

        action_name = action.get("name", "unknown")
        status = outcome.get("status", "")
        confidence = state.self_model.setdefault("confidence_profile", {})

        if status == "ok":
            confidence[action_name] = min(1.0, confidence.get(action_name, 0.5) + 0.1)
            state.regulation["continuity_health"] = min(1.0, state.regulation.get("continuity_health", 0.8) + 0.02)
            state.regulation["error_accumulation"] = max(0.0, state.regulation.get("error_accumulation", 0.0) - 0.01)
        elif status in ("error", "blocked"):
            confidence[action_name] = max(0.0, confidence.get(action_name, 0.5) - 0.15)
            state.regulation["error_accumulation"] = min(1.0, state.regulation.get("error_accumulation", 0.0) + 0.05)
            state.regulation["continuity_health"] = max(0.0, state.regulation.get("continuity_health", 0.8) - 0.01)
            state.self_model.setdefault("recent_failures", []).append(
                {"action": action_name, "cycle_id": state.cycle_id}
            )
            state.self_model["recent_failures"] = state.self_model["recent_failures"][-10:]

        return state
