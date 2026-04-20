from subjective_runtime_v2_1.engines.interpretive_bias import InterpretiveBiasEngine
from subjective_runtime_v2_1.modules.language import LanguageModule
from subjective_runtime_v2_1.state.models import AgentStateV2_1, RawObservation, ValenceSignal


def test_raw_observation_survives_bias_shift():
    state = AgentStateV2_1()
    obs = RawObservation("sensor", "text", {"text": "alert"}, 1.0, 0.0)
    state.raw_observations.append(obs)
    state.continuity_field.active_themes = ["steady"]

    base_bias = InterpretiveBiasEngine().derive(state)
    cand1 = LanguageModule().run(state, {"text": "alert"}, base_bias)[0]

    state.valuation_field = [ValenceSignal("steady", "threatening", 0.8, "test", 0.0)]
    threat_bias = InterpretiveBiasEngine().derive(state)
    cand2 = LanguageModule().run(state, {"text": "alert"}, threat_bias)[0]

    assert state.raw_observations[-1].payload["text"] == "alert"
    assert cand1.salience != cand2.salience or cand1.valuation_alignment != cand2.valuation_alignment
