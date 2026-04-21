from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime():
    registry = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


def test_repeated_failure_pushes_toward_exploit_and_higher_burden():
    runtime = build_runtime()
    r1 = runtime.cycle("r", {"text": "start", "observed_status": "stable"})
    s1 = r1.new_state
    s1.self_model["limits"]["blocked_tools"] = ["echo", "memory_write"]
    runtime.state_store.save("r", s1)
    r2 = runtime.cycle("r", {"text": "again", "observed_status": "degraded"})
    r3 = runtime.cycle("r", {"text": "again", "observed_status": "degraded"})
    assert r3.new_state.regulation["unresolved_loop_burden"] >= r2.new_state.regulation["unresolved_loop_burden"]
    assert r3.new_state.cognitive_mode == "EXPLOIT"
