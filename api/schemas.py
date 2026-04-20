from pydantic import BaseModel, Field


class RunConfigModel(BaseModel):
    tick_interval_sec: float = 0.2
    idle_enabled: bool = True
    auto_sleep_when_stable: bool = True
    stability_threshold: float = 0.92


class RunCreateRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)
    config: RunConfigModel = Field(default_factory=RunConfigModel)


class InputRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)


class CycleRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)
    idle_tick: bool = False
