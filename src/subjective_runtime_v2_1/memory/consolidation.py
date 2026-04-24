from __future__ import annotations

from collections import Counter

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class ConsolidationEngine:
    def run(self, state: AgentStateV2_1) -> AgentStateV2_1:
        recent = state.episodic_trace[-8:]
        tension_counter: Counter[str] = Counter()
        action_counter: Counter[str] = Counter()
        for item in recent:
            for t in item.get("tensions", []):
                tension_counter[t] += 1
            a = (item.get("last_action") or {}).get("name")
            if a:
                action_counter[a] += 1

        duplicates = sum(c - 1 for c in action_counter.values() if c > 1)
        state.regulation["memory_pressure"] = max(0.0, state.regulation.get("memory_pressure", 0.0) - min(0.05, duplicates * 0.01))
        state.last_consolidation = {
            "recent_episodes": len(recent),
            "top_tensions": tension_counter.most_common(3),
            "top_actions": action_counter.most_common(3),
            "duplicate_actions": duplicates,
        }
        if duplicates and state.last_consolidation not in state.working_memory:
            state.working_memory.append({"kind": "consolidation_summary", **state.last_consolidation})
            state.working_memory = state.working_memory[-10:]
        return state
