from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime():
    registry = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


def test_repeated_blocked_actions_increase_burden():
    runtime = build_runtime()
    result = runtime.cycle("r1", {"text": "start", "observed_status": "degraded"})
    state = result.new_state
    # force a high-risk path by blocking echo tool
    state.self_model["limits"]["blocked_tools"] = ["echo"]
    runtime.state_store.save("r1", state)
    result2 = runtime.cycle("r1", {"text": "again", "observed_status": "degraded"})
    assert result2.new_state.regulation["unresolved_loop_burden"] >= state.regulation["unresolved_loop_burden"]


def test_stable_success_preserves_or_improves_continuity():
    runtime = build_runtime()
    r1 = runtime.cycle("r2", {"text": "check", "observed_status": "stable"})
    r2 = runtime.cycle("r2", {"text": "check", "observed_status": "stable"})
    assert r2.new_state.regulation["continuity_health"] >= r1.new_state.regulation["continuity_health"] - 0.1
