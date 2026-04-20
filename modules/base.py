from __future__ import annotations

from abc import ABC, abstractmethod

from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias


class Module(ABC):
    name: str

    @abstractmethod
    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        raise NotImplementedError
