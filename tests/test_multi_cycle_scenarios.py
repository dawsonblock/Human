from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime():
    registry = build_tool_registry(memory_sink=[], allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


def test_repeated_blocked_actions_increase_burden():
    runtime = build_runtime()
    state = runtime.cycle("r1", {"text": "start", "observed_status": "degraded"})
    # force a high-risk path by blocking echo tool
    state.self_model["limits"]["blocked_tools"] = ["echo"]
    runtime.state_store.save("r1", state)
    state2 = runtime.cycle("r1", {"text": "again", "observed_status": "degraded"})
    assert state2.regulation["unresolved_loop_burden"] >= state.regulation["unresolved_loop_burden"]


def test_stable_success_preserves_or_improves_continuity():
    runtime = build_runtime()
    s1 = runtime.cycle("r2", {"text": "check", "observed_status": "stable"})
    s2 = runtime.cycle("r2", {"text": "check", "observed_status": "stable"})
    assert s2.regulation["continuity_health"] >= s1.regulation["continuity_health"] - 0.1
