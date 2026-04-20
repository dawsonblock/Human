from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate
from subjective_runtime_v2_1.workspace.attention import AttentionGate


def test_dynamic_attention_ranks_differently_by_mode():
    gate = AttentionGate(max_focus_items=1)
    novelty = Candidate("1", "x", "novel", {}, 1.0, 0.4, 0.2, novelty=0.9, information_gain=0.8)
    goal = Candidate("2", "x", "goal", {}, 1.0, 0.5, 0.9, novelty=0.1, information_gain=0.1)

    s = AgentStateV2_1()
    s.cognitive_mode = "EXPLORE"
    s.risk_appetite = 0.8
    assert gate.select([novelty, goal], s)[0].id == "1"

    s.cognitive_mode = "EXPLOIT"
    s.risk_appetite = 0.1
    assert gate.select([novelty, goal], s)[0].id == "2"
