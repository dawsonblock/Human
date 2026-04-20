from subjective_runtime_v2_1.memory.system import MemorySystem
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_memory_system_reads_and_writes():
    state = AgentStateV2_1()
    MemorySystem().write_episode(state, {"cycle_id": 1})
    retrieved = MemorySystem().retrieve(state)
    assert retrieved["episodic"][-1]["cycle_id"] == 1
