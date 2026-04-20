from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, ContinuityTrace


class ContinuityEngine:
    """Build a ContinuityTrace capturing active goals, recent events, and open loops."""

    def update(self, state: AgentStateV2_1) -> ContinuityTrace:
        active_themes: list[str] = []
        for goal in state.goal_stack:
            name = goal.get("name")
            if name and name not in active_themes:
                active_themes.append(name)
        for theme in state.continuity_field.active_themes:
            if theme not in active_themes:
                active_themes.append(theme)
        active_themes = active_themes[:8]

        recent_events: list[dict] = list(state.continuity_field.recent_events)
        if state.last_action:
            recent_events.append({"action": dict(state.last_action), "cycle_id": state.cycle_id})
        recent_events = recent_events[-16:]

        open_loops: list[dict] = list(state.continuity_field.open_loops)
        if state.last_outcome and state.last_outcome.get("status") in ("error", "blocked"):
            loop = {
                "action": (state.last_action or {}).get("name", "unknown"),
                "cycle_id": state.cycle_id,
                "reason": state.last_outcome.get("reason", state.last_outcome.get("error", "unknown")),
            }
            open_loops.append(loop)
        open_loops = [lp for lp in open_loops if lp.get("cycle_id", 0) > state.cycle_id - 12]

        tension_load = min(1.0, len(state.tensions) * 0.15)
        recency_weight = min(0.95, 0.5 + tension_load * 0.3)
        momentum_weight = min(0.95, 0.5 + len(active_themes) * 0.05)

        return ContinuityTrace(
            summary=active_themes[0] if active_themes else "idle",
            recent_events=recent_events,
            active_themes=active_themes,
            open_loops=open_loops,
            recency_weight=recency_weight,
            momentum_weight=momentum_weight,
        )
