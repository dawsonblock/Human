from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime():
    registry = build_tool_registry(memory_sink=[], allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


def test_repeated_failure_pushes_toward_exploit_and_higher_burden():
    runtime = build_runtime()
    s1 = runtime.cycle("r", {"text": "start", "observed_status": "stable"})
    s1.self_model["limits"]["blocked_tools"] = ["echo", "memory_write"]
    runtime.state_store.save("r", s1)
    s2 = runtime.cycle("r", {"text": "again", "observed_status": "degraded"})
    s3 = runtime.cycle("r", {"text": "again", "observed_status": "degraded"})
    assert s3.regulation["unresolved_loop_burden"] >= s2.regulation["unresolved_loop_burden"]
    assert s3.cognitive_mode == "EXPLOIT"
