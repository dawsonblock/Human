from subjective_runtime_v2_1.engines.valuation import ValuationEngine
from subjective_runtime_v2_1.state.models import AgentStateV2_1


def test_success_yields_relief_or_coherence():
    state = AgentStateV2_1()
    state.last_action = {"name": "demo"}
    state.last_outcome = {"status": "ok"}
    signals = ValuationEngine().update(state)
    kinds = {s.kind for s in signals}
    assert "relieving" in kinds or "coherent" in kinds


def test_failure_yields_costly_or_threatening():
    state = AgentStateV2_1()
    state.last_action = {"name": "demo"}
    state.last_outcome = {"status": "error"}
    signals = ValuationEngine().update(state)
    kinds = {s.kind for s in signals}
    assert "costly" in kinds or "threatening" in kinds
