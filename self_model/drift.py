from __future__ import annotations

from collections import Counter


class DriftAnalyzer:
    def summarize(self, self_history: list[dict]) -> dict:
        names = [e.get("action") for e in self_history if e.get("action")]
        top = Counter(names).most_common(3)
        return {"top_actions": top}
