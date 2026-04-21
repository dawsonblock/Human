from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1, ValenceSignal
from subjective_runtime_v2_1.util.time import now_ts


class ValuationEngine:
    """Produce valence signals based on the outcome of the last action."""

    def update(self, state: AgentStateV2_1) -> list[ValenceSignal]:
        outcome = state.last_outcome
        action = state.last_action
        if not outcome or not action:
            return state.valuation_field

        action_name = action.get("name", "unknown")
        status = outcome.get("status", "")
        ts = now_ts()

        signals: list[ValenceSignal] = list(state.valuation_field)

        if status == "ok":
            signals.append(ValenceSignal(
                target=action_name,
                kind="relieving",
                magnitude=0.4,
                source="valuation_engine",
                timestamp=ts,
                decay_class="fast",
            ))
            signals.append(ValenceSignal(
                target=action_name,
                kind="coherent",
                magnitude=0.3,
                source="valuation_engine",
                timestamp=ts,
                decay_class="medium",
            ))
        elif status in ("error", "blocked"):
            signals.append(ValenceSignal(
                target=action_name,
                kind="costly",
                magnitude=0.5,
                source="valuation_engine",
                timestamp=ts,
                decay_class="medium",
            ))
            signals.append(ValenceSignal(
                target=action_name,
                kind="threatening",
                magnitude=0.3,
                source="valuation_engine",
                timestamp=ts,
                decay_class="slow",
            ))

        return signals[-24:]
