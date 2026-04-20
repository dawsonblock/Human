from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    side_effect_level: str
    requires_confirmation: bool = False
    allowed_in_idle: bool = False
    timeout_sec: float = 10.0
    reversibility: str = "unknown"
    observability: str = "high"
    blast_radius: str = "low"
    audit_required: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    origin: str = "planner"
    dry_run: bool = False


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: dict[str, Any]
    error: str | None = None
    latency_ms: float | None = None
    memory_writes: list[dict[str, Any]] = field(default_factory=list)
    state_delta: dict[str, Any] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)
