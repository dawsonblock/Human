from __future__ import annotations

from dataclasses import asdict
from pprint import pprint

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def build_runtime() -> RuntimeCore:
    memory_sink: list[dict] = []
    registry = build_tool_registry(memory_sink=memory_sink, allowed_roots=["."])
    return RuntimeCore(
        state_store=InMemoryStateStore(),
        gate=ActionGate(registry),
        executor=Executor(registry),
    )


if __name__ == "__main__":
    runtime = build_runtime()
    state = runtime.cycle("demo", {"text": "check system coherence", "observed_status": "degraded"})
    pprint(asdict(state))
