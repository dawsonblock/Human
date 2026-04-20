from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class TriggerEvaluator:
    def should_force_active_tick(self, state: AgentStateV2_1) -> tuple[bool, str]:
        if any(t.severity > 0.7 for t in state.tensions):
            return True, 'high_severity_tension'
        if state.regulation.get('continuity_health', 1.0) < 0.5:
            return True, 'low_continuity'
        if state.regulation.get('error_accumulation', 0.0) > 0.6:
            return True, 'error_accumulation'
        return False, 'stable'
