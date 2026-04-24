from __future__ import annotations

from subjective_runtime_v2_1.action.registry import ToolRegistry
from subjective_runtime_v2_1.planning.policies import IDLE_ALLOWED_TOOLS
from subjective_runtime_v2_1.state.models import AgentStateV2_1, ActionOption


class ActionGate:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def approve(self, state: AgentStateV2_1, action: ActionOption, idle_tick: bool = False) -> tuple[bool, str]:
        tool_name = action.target.get("tool_name")
        if not tool_name:
            return False, "blocked: no tool target"
        try:
            spec = self.registry.get(tool_name).spec
        except KeyError:
            return False, "blocked: unknown tool"
        if tool_name in state.self_model.get("limits", {}).get("blocked_tools", []):
            return False, "blocked: tool restricted"
        if idle_tick and tool_name not in IDLE_ALLOWED_TOOLS:
            return False, "blocked: tool not allowed during idle autonomy"
        if spec.requires_confirmation:
            return False, "approval_required"
        if spec.blast_radius == "high" and action.estimated_risk > 0.2:
            return False, "blocked: blast radius too high"
        return True, "approved"
