from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, NarrativeFrame


class NarrativeEngine:
    def build_pre(self, state: AgentStateV2_1) -> NarrativeFrame:
        goal = state.goal_stack[0].get("name", "no_goal") if state.goal_stack else "no_goal"
        tension = state.tensions[0].kind if state.tensions else "none"
        position = "strained" if state.regulation.get("continuity_health", 1.0) < 0.5 else "stable"
        return NarrativeFrame(
            current_scene=f"operating under goal={goal}",
            self_position=position,
            main_concern=tension,
            active_goal_meaning=f"current direction is {goal}",
            recent_change=str(state.last_outcome) if state.last_outcome else "no recent change",
            next_expected_turn="stabilize" if position == "strained" else "continue",
            confidence=max(0.0, min(1.0, state.regulation.get("continuity_health", 0.0))),
        )

    def build_post(self, state: AgentStateV2_1) -> NarrativeFrame:
        focus = state.active_focus[0].kind if state.active_focus else "none"
        action = state.last_action.get("name") if state.last_action else "none"
        return NarrativeFrame(
            current_scene=f"focus={focus}",
            self_position="stable" if state.regulation.get("overload_pressure", 0.0) < 0.5 else "strained",
            main_concern=state.pre_narrative.main_concern,
            active_goal_meaning=state.pre_narrative.active_goal_meaning,
            recent_change=f"action={action} outcome={state.last_outcome}",
            next_expected_turn="observe" if not state.pending_options else "evaluate",
            confidence=0.7 if state.active_focus else 0.3,
        )
