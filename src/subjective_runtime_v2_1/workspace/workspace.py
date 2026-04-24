from __future__ import annotations

from subjective_runtime_v2_1.state.models import Candidate


class Workspace:
    """Transient workspace holding candidates for the current cognitive cycle."""

    def __init__(self) -> None:
        self._items: list[Candidate] = []

    def clear(self) -> None:
        self._items = []

    def add(self, candidate: Candidate) -> None:
        self._items.append(candidate)

    def all(self) -> list[Candidate]:
        return list(self._items)
