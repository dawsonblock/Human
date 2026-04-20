from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionContext:
    run_id: str
    cycle_id: int
    idle_tick: bool
    policies: dict
    self_model: dict
    world_model: dict
    regulation: dict
