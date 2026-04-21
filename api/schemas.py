from __future__ import annotations

from pydantic import BaseModel, Field


class RunConfigModel(BaseModel):
    tick_interval_sec: float = 0.2
    idle_enabled: bool = True
    auto_sleep_when_stable: bool = True
    stability_threshold: float = 0.92
    max_cycles: int = 0
    max_actions: int = 0
    max_replans: int = 3


class GoalRequest(BaseModel):
    type: str = "operator_request"
    description: str
    priority: float = 0.5
    success_criteria: str = ""


class RunCreateRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)
    config: RunConfigModel = Field(default_factory=RunConfigModel)
    goal: GoalRequest | None = None


class InputRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    action_id: str
