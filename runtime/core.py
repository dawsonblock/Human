from __future__ import annotations

from dataclasses import asdict

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.config import RuntimeConfig
from subjective_runtime_v2_1.engines.cognitive_mode import CognitiveModeEngine
from subjective_runtime_v2_1.engines.conflict import ConflictEngine
from subjective_runtime_v2_1.engines.consequence import ConsequenceEngine
from subjective_runtime_v2_1.engines.continuity import ContinuityEngine
from subjective_runtime_v2_1.engines.homeostasis import HomeostasisEngine
from subjective_runtime_v2_1.engines.hypothesis import HypothesisEngine
from subjective_runtime_v2_1.engines.interpretive_bias import InterpretiveBiasEngine
from subjective_runtime_v2_1.engines.narrative import NarrativeEngine
from subjective_runtime_v2_1.engines.valuation import ValuationEngine
from subjective_runtime_v2_1.memory.consolidation import ConsolidationEngine
from subjective_runtime_v2_1.memory.system import MemorySystem
from subjective_runtime_v2_1.modules.associative import AssociativeModule
from subjective_runtime_v2_1.modules.discrepancy import DiscrepancyModule
from subjective_runtime_v2_1.modules.language import LanguageModule
from subjective_runtime_v2_1.modules.prediction import PredictionModule
from subjective_runtime_v2_1.modules.reflection import ReflectionModule
from subjective_runtime_v2_1.modules.rehearsal import RehearsalModule
from subjective_runtime_v2_1.modules.self_check import SelfCheckModule
from subjective_runtime_v2_1.planning.planner import Planner
from subjective_runtime_v2_1.planning.scoring import score_action
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, RawObservation, Tension
from subjective_runtime_v2_1.state.store import InMemoryStateStore
from subjective_runtime_v2_1.tension.engine import TensionEngine
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts
from subjective_runtime_v2_1.workspace.attention import AttentionGate
from subjective_runtime_v2_1.workspace.workspace import Workspace


class RuntimeCore:
    def __init__(
        self,
        state_store: InMemoryStateStore,
        gate: ActionGate,
        executor: Executor,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.state_store = state_store
        self.config = config or RuntimeConfig()
        self.workspace = Workspace()
        self.attention = AttentionGate(self.config)
        self.valuation = ValuationEngine()
        self.continuity = ContinuityEngine()
        self.conflict = ConflictEngine()
        self.narrative = NarrativeEngine()
        self.bias_engine = InterpretiveBiasEngine()
        self.consequence = ConsequenceEngine()
        self.homeostasis = HomeostasisEngine()
        self.mode_engine = CognitiveModeEngine(self.config)
        self.hypotheses = HypothesisEngine()
        self.tensions = TensionEngine()
        self.memory = MemorySystem()
        self.consolidation = ConsolidationEngine()
        self.planner = Planner()
        self.gate = gate
        self.executor = executor
        self.modules = [
            LanguageModule(),
            PredictionModule(),
            DiscrepancyModule(),
            RehearsalModule(),
            ReflectionModule(),
            SelfCheckModule(),
        ]
        self.associative = AssociativeModule()

    def cycle(self, run_id: str, inputs: dict, idle_tick: bool = False) -> AgentStateV2_1:
        state = self.state_store.load(run_id)
        state.cycle_id += 1
        state.timestamp = now_ts()

        state.interpreted_percepts["idle_tick"] = idle_tick
        if inputs:
            state.raw_observations.append(RawObservation(
                source="external_input",
                modality="mixed",
                payload=dict(inputs),
                confidence=1.0,
                timestamp=state.timestamp,
                provenance={"run_id": run_id, "cycle_id": state.cycle_id},
            ))
        if "observed_status" in inputs:
            state.interpreted_percepts["status"] = inputs["observed_status"]
        if "text" in inputs:
            state.interpreted_percepts["latest_text"] = inputs["text"]

        state.continuity_field = self.continuity.update(state)
        state = self.consequence.apply(state)
        state = self.homeostasis.update(state)
        state = self.mode_engine.update(state)
        state.valuation_field = self.valuation.update(state)
        state.conflict_field = self.conflict.update(state)
        memories = self.memory.retrieve(state)
        state.interpretive_bias = self.bias_engine.derive(state)

        self.workspace.clear()
        for module in self.modules:
            for c in module.run(state, inputs, state.interpretive_bias):
                self.workspace.add(c)

        state.tensions = self.tensions.generate(state)
        if "status" in state.interpreted_percepts and state.world_model.get("expected_status") and state.interpreted_percepts["status"] != state.world_model.get("expected_status"):
            state.tensions.append(Tension(kind="discrepancy", severity=0.7, description="Observed state differs from expected state"))

        state = self.hypotheses.generate(state)
        for h in state.hypotheses:
            self.workspace.add(Candidate(
                id=new_id("cand"),
                source="hypothesis_engine",
                kind="hypothesis",
                content=h,
                confidence=h.get("confidence", 0.3),
                salience=0.45,
                goal_relevance=0.35,
                uncertainty_reduction=0.30,
                novelty=0.25,
                recency=0.9,
                valuation_alignment=0.2,
                continuity_match=0.2,
                conflict_pressure=0.15,
                information_gain=0.45,
            ))

        for c in self.associative.run(state, inputs, state.interpretive_bias):
            self.workspace.add(c)

        state.pre_narrative = self.narrative.build_pre(state)
        for m in memories.get("episodic", [])[-2:]:
            self.workspace.add(Candidate(
                id=new_id("cand"),
                source="memory",
                kind="episodic_memory",
                content=m,
                confidence=0.7,
                salience=0.2,
                goal_relevance=0.3,
                uncertainty_reduction=0.0,
                novelty=0.0,
                recency=0.7,
                valuation_alignment=0.0,
                continuity_match=state.interpretive_bias.continuity_bias,
                conflict_pressure=0.0,
                information_gain=0.05,
            ))

        state.active_focus = self.attention.select(self.workspace.all(), state)
        state.post_narrative = self.narrative.build_post(state)
        state.pending_options = self.planner.propose(state)
        if state.pending_options:
            ranked = sorted(state.pending_options, key=lambda a: score_action(a, self.config, state), reverse=True)
            chosen = ranked[0]
            approved, reason = self.gate.approve(state, chosen, idle_tick=idle_tick)
            state.last_action = {"id": chosen.id, "name": chosen.name, "gate_reason": reason}
            if approved:
                ctx = ExecutionContext(
                    run_id=run_id,
                    cycle_id=state.cycle_id,
                    idle_tick=idle_tick,
                    policies={},
                    self_model=state.self_model,
                    world_model=state.world_model,
                    regulation=state.regulation,
                )
                state.last_outcome = self.executor.execute(chosen, ctx)
            elif reason == "approval_required":
                state.approval_requests.append({
                    "action_id": chosen.id,
                    "tool_name": chosen.target.get("tool_name"),
                    "arguments": chosen.target.get("arguments", {}),
                    "reason": chosen.name,
                    "created_at": state.timestamp,
                    "status": "pending",
                })
                state.last_outcome = {"status": "blocked", "reason": reason}
            else:
                state.last_outcome = {"status": "blocked", "reason": reason}

        if idle_tick:
            state = self.consolidation.run(state)

        self.memory.write_episode(state, {
            "cycle_id": state.cycle_id,
            "tensions": [t.kind for t in state.tensions],
            "pre_narrative": asdict(state.pre_narrative),
            "post_narrative": asdict(state.post_narrative),
            "last_action": state.last_action,
            "last_outcome": state.last_outcome,
        })
        self.state_store.save(run_id, state)
        return state
