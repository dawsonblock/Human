from subjective_runtime_v2_1.state.models import Candidate
from subjective_runtime_v2_1.workspace.attention import AttentionGate


def test_attention_selects_highest_scored():
    gate = AttentionGate(max_focus_items=1)
    a = Candidate("1", "x", "low", {}, 1.0, 0.1, 0.1)
    b = Candidate("2", "x", "high", {}, 1.0, 0.9, 0.8)
    chosen = gate.select([a, b])
    assert chosen[0].id == "2"
