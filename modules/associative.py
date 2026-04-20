from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class AssociativeModule(Module):
    name = "associative"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if state.cognitive_mode != "EXPLORE":
            return []
        window = state.working_memory[-5:]
        if len(window) < 2:
            return []

        # Group items by kind; pick the two most recent items that differ in kind.
        seen_kinds: dict[str, dict] = {}
        for item in reversed(window):
            k = item.get("kind", "memory")
            if k not in seen_kinds:
                seen_kinds[k] = item
            if len(seen_kinds) >= 2:
                break

        if len(seen_kinds) < 2:
            return []

        kinds = list(seen_kinds.keys())
        kind_a, kind_b = kinds[0], kinds[1]
        item_a, item_b = seen_kinds[kind_a], seen_kinds[kind_b]

        recency_a = item_a.get("cycle_id", 0)
        recency_b = item_b.get("cycle_id", 0)
        recency_score = 0.5 + 0.5 * min(recency_a, recency_b) / max(max(recency_a, recency_b), 1)

        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="associative_bridge",
            content={
                "bridge": f"Link {kind_a} with {kind_b}",
                "from": [kind_a, kind_b],
            },
            confidence=0.55,
            salience=0.45,
            goal_relevance=0.25,
            uncertainty_reduction=0.05,
            novelty=0.7,
            recency=recency_score,
            valuation_alignment=0.1,
            continuity_match=0.2,
            conflict_pressure=0.0,
            information_gain=0.35,
        )]
