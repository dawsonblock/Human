from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime():
    registry = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


def test_idle_tick_runs_consolidation():
    runtime = build_runtime()
    runtime.cycle("r", {"text": "start"}, idle_tick=False)
    result = runtime.cycle("r", {}, idle_tick=True)
    assert "recent_episodes" in result.new_state.last_consolidation
