from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, ActionOption
from subjective_runtime_v2_1.util.ids import new_id

_DEFAULT_CAPABILITIES: dict[str, bool] = {
    "echo": True,
    "memory_write": True,
    "file_read": True,
    "file_write": True,
    "http_get": False,
}
# Treat as read-only; do not mutate this dict at runtime.


class Planner:
    def propose(self, state: AgentStateV2_1) -> list[ActionOption]:
        caps: dict = state.self_model.get("capabilities", _DEFAULT_CAPABILITIES)
        options: list[ActionOption] = []

        # echo is a communicative / internal-narration action, not a hypothesis probe.
        if caps.get("echo", True) and state.tensions:
            options.append(ActionOption(
                id=new_id("act"),
                name="echo_status",
                target={"tool_name": "echo", "arguments": {"message": state.pre_narrative.current_scene}},
                predicted_world_effect={},
                predicted_self_effect={"continuity_health": 0.01},
                expected_value=0.45,
                estimated_cost=0.02,
                estimated_risk=0.01,
                tension_reduction=0.10,
                uncertainty_reduction=0.05,
                continuity_preservation=0.15,
                valuation_alignment=0.10,
                narrative_fit=0.12,
                conflict_resolution_value=0.02,
                information_gain=0.02,
            ))

        # Hypothesis testing only uses capabilities that can actually probe.
        # With no external affordances, narrate internally via memory_write.
        for h in state.hypotheses[:3]:
            if caps.get("memory_write", True):
                # Record the hypothesis in self_history — honest epistemic maintenance.
                options.append(ActionOption(
                    id=new_id("act"),
                    name=f"note_hypothesis_{h['kind']}",
                    target={
                        "tool_name": "memory_write",
                        "arguments": {
                            "kind": "self_history",
                            "payload": {
                                "kind": "hypothesis_note",
                                "hypothesis_kind": h["kind"],
                                "confidence": h.get("confidence", 0.0),
                                "cycle_id": state.cycle_id,
                            },
                        },
                    },
                    predicted_world_effect={},
                    predicted_self_effect={"uncertainty_load": -0.05},
                    expected_value=0.35 + h.get("confidence", 0.0) * 0.2,
                    estimated_cost=0.02,
                    estimated_risk=0.01,
                    tension_reduction=0.08,
                    uncertainty_reduction=0.22,
                    continuity_preservation=0.06,
                    valuation_alignment=0.08,
                    narrative_fit=0.10,
                    conflict_resolution_value=0.12,
                    information_gain=0.35,
                ))

        if caps.get("memory_write", True) and state.regulation.get("unresolved_loop_burden", 0.0) > 0.4:
            options.append(ActionOption(
                id=new_id("act"),
                name="reflect_and_consolidate",
                target={
                    "tool_name": "memory_write",
                    "arguments": {
                        "kind": "self_history",
                        "payload": {"kind": "reflection", "cycle_id": state.cycle_id},
                    },
                },
                predicted_world_effect={},
                predicted_self_effect={"unresolved_loop_burden": -0.05},
                expected_value=0.30,
                estimated_cost=0.02,
                estimated_risk=0.01,
                tension_reduction=0.18,
                uncertainty_reduction=0.08,
                continuity_preservation=0.25,
                valuation_alignment=0.12,
                narrative_fit=0.15,
                conflict_resolution_value=0.08,
                information_gain=0.10,
            ))

        if state.goal_stack:
            goal_name = state.goal_stack[0].get("name", "goal")
            if caps.get("echo", True):
                options.append(ActionOption(
                    id=new_id("act"),
                    name="continue_goal",
                    target={"tool_name": "echo", "arguments": {"message": f"continue:{goal_name}"}},
                    predicted_world_effect={"goal_progress": True},
                    predicted_self_effect={"continuity_health": 0.02},
                    expected_value=0.55,
                    estimated_cost=0.03,
                    estimated_risk=0.02,
                    tension_reduction=0.06,
                    uncertainty_reduction=0.04,
                    continuity_preservation=0.24,
                    valuation_alignment=0.14,
                    narrative_fit=0.18,
                    conflict_resolution_value=0.04,
                    information_gain=0.03,
                ))
        return options

