from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ApprovalRequest:
    run_id: str
    action_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    created_at: float
    status: str = "pending"
