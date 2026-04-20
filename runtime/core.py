from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

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

WORKING_MEMORY_CAP = 12  # max items; older entries are evicted to keep the buffer compact


@dataclass
class CycleResult:
    """Pure output of a single cognitive cycle.

    RuntimeCore produces this object.  The supervisor (or test harness) is
    responsible for persisting ``new_state`` and ``events`` atomically via
    ``SQLiteRunStore.apply_cycle_transition``.
    """
    new_state: AgentStateV2_1
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    tool_records: list[dict[str, Any]] = field(default_factory=list)
    approval_requests: list[dict[str, Any]] = field(default_factory=list)
    cycle_summary: dict[str, Any] = field(default_factory=dict)


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cycle(self, run_id: str, inputs: dict, idle_tick: bool = False) -> CycleResult:
        """Run one cognitive cycle and return a CycleResult.

        RuntimeCore does NOT persist the resulting state; that is the caller's
        responsibility.  The only exception is the internal InMemoryStateStore
        used as a cycle-to-cycle buffer — that save is done here so that
        successive direct calls (e.g. in unit tests) see a consistent state.
        """
        state = self.state_store.load(run_id)
        state.cycle_id += 1
        state.timestamp = now_ts()

        # ---- perception ----
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

        # ---- engines ----
        state.continuity_field = self.continuity.update(state)
        state = self.consequence.apply(state)
        state = self.homeostasis.update(state)
        state = self.mode_engine.update(state)
        state.valuation_field = self.valuation.update(state)
        state.conflict_field = self.conflict.update(state)
        memories = self.memory.retrieve(state)
        state.interpretive_bias = self.bias_engine.derive(state)

        # ---- workspace population ----
        self.workspace.clear()
        for module in self.modules:
            for c in module.run(state, inputs, state.interpretive_bias):
                self.workspace.add(c)

        state.tensions = self.tensions.generate(state)
        if (
            "status" in state.interpreted_percepts
            and state.world_model.get("expected_status")
            and state.interpreted_percepts["status"] != state.world_model.get("expected_status")
        ):
            state.tensions.append(Tension(
                kind="discrepancy",
                severity=0.7,
                description="Observed state differs from expected state",
            ))

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

        # ---- planning and execution ----
        new_approval: dict[str, Any] | None = None
        tool_record: dict[str, Any] | None = None

        state.pending_options = self.planner.propose(state)
        if state.pending_options:
            ranked = sorted(
                state.pending_options,
                key=lambda a: score_action(a, self.config, state),
                reverse=True,
            )
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
                outcome = self.executor.execute(chosen, ctx)
                state.last_outcome = outcome
                tool_record = dict(outcome)
                self._apply_tool_mutations(state, outcome)
            elif reason == "approval_required":
                req = {
                    "action_id": chosen.id,
                    "tool_name": chosen.target.get("tool_name"),
                    "arguments": chosen.target.get("arguments", {}),
                    "reason": chosen.name,
                    "created_at": state.timestamp,
                    "status": "pending",
                }
                state.approval_requests.append(req)
                new_approval = req
                state.last_outcome = {"status": "blocked", "reason": reason}
            else:
                state.last_outcome = {"status": "blocked", "reason": reason}

        # ---- consolidation (idle ticks only) ----
        if idle_tick:
            state = self.consolidation.run(state)

        # ---- episodic trace ----
        self.memory.write_episode(state, {
            "cycle_id": state.cycle_id,
            "tensions": [t.kind for t in state.tensions],
            "pre_narrative": asdict(state.pre_narrative),
            "post_narrative": asdict(state.post_narrative),
            "last_action": state.last_action,
            "last_outcome": state.last_outcome,
        })

        # ---- working memory promotion ----
        self._promote_working_memory(state, memories)

        # ---- persist to internal buffer (for unit-test compat) ----
        self.state_store.save(run_id, state)

        # ---- build CycleResult ----
        events = self._build_cycle_events(state, idle_tick, tool_record, new_approval)
        tool_records = [tool_record] if tool_record else []
        approval_requests = [new_approval] if new_approval else []

        return CycleResult(
            new_state=state,
            events=events,
            tool_records=tool_records,
            approval_requests=approval_requests,
            cycle_summary={
                "cycle_id": state.cycle_id,
                "idle_tick": idle_tick,
                "cognitive_mode": state.cognitive_mode,
                "tension_count": len(state.tensions),
                "focus_kinds": [c.kind for c in state.active_focus],
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_tool_mutations(self, state: AgentStateV2_1, outcome: dict) -> None:
        """Apply memory_writes and state_delta from tool execution to state."""
        for entry in outcome.get("memory_writes") or []:
            kind = entry.get("kind")
            payload = entry.get("payload", {})
            cycle_id = entry.get("cycle_id", state.cycle_id)
            record = {"kind": kind, "payload": payload, "cycle_id": cycle_id}
            if kind == "working_note":
                state.working_memory.append(record)
                state.working_memory = state.working_memory[-WORKING_MEMORY_CAP:]
            elif kind == "episode":
                state.episodic_trace.append(record)
            elif kind == "self_history":
                state.self_history.append(record)

        delta = outcome.get("state_delta") or {}
        if "regulation" in delta and isinstance(delta["regulation"], dict):
            for k, v in delta["regulation"].items():
                if isinstance(v, (int, float)):
                    state.regulation[k] = float(v)
        if "world_model" in delta and isinstance(delta["world_model"], dict):
            state.world_model.update(delta["world_model"])

    def _promote_working_memory(self, state: AgentStateV2_1, memories: dict) -> None:
        """Promote key cycle artifacts into working memory each cycle."""
        wm = state.working_memory
        cycle_id = state.cycle_id

        if state.active_focus:
            wm.append({
                "kind": "focus_summary",
                "cycle_id": cycle_id,
                "focus_kinds": [c.kind for c in state.active_focus[:3]],
            })

        if state.last_outcome and state.last_outcome.get("status") == "ok":
            wm.append({
                "kind": "tool_success",
                "cycle_id": cycle_id,
                "tool_name": state.last_outcome.get("tool_name"),
                "result": state.last_outcome.get("result"),
            })
        elif state.last_outcome and state.last_outcome.get("status") in ("error", "blocked"):
            wm.append({
                "kind": "tool_failure",
                "cycle_id": cycle_id,
                "tool_name": state.last_outcome.get("tool_name"),
                "reason": state.last_outcome.get("reason") or state.last_outcome.get("error"),
            })

        if state.hypotheses:
            top_h = max(state.hypotheses, key=lambda h: h.get("confidence", 0.0))
            wm.append({
                "kind": "top_hypothesis",
                "cycle_id": cycle_id,
                "hypothesis_kind": top_h.get("kind"),
                "confidence": top_h.get("confidence"),
            })

        if state.tensions:
            top_t = max(state.tensions, key=lambda t: t.severity)
            wm.append({
                "kind": "tension_summary",
                "cycle_id": cycle_id,
                "tension_kind": top_t.kind,
                "severity": top_t.severity,
            })

        if state.approval_requests:
            latest = state.approval_requests[-1]
            if latest.get("status") == "pending":
                wm.append({
                    "kind": "approval_pending",
                    "cycle_id": cycle_id,
                    "action_id": latest.get("action_id"),
                    "tool_name": latest.get("tool_name"),
                })

        state.working_memory = wm[-WORKING_MEMORY_CAP:]

    def _build_cycle_events(
        self,
        state: AgentStateV2_1,
        idle_tick: bool,
        tool_record: dict | None,
        new_approval: dict | None,
    ) -> list[tuple[str, dict]]:
        """Collect all cycle-scoped events as (event_type, payload) pairs."""
        events: list[tuple[str, dict]] = []

        if state.last_action is not None:
            events.append((
                "tool_call_proposed",
                {"cycle_id": state.cycle_id, "last_action": state.last_action},
            ))

        if tool_record is not None:
            event_type = "tool_call_executed" if tool_record.get("status") == "ok" else "tool_call_failed"
            events.append((
                event_type,
                {
                    "cycle_id": state.cycle_id,
                    "last_action": state.last_action,
                    "last_outcome": state.last_outcome,
                },
            ))

        if new_approval is not None:
            events.append(("approval_requested", dict(new_approval)))

        events.append((
            "cycle_completed",
            {
                "cycle_id": state.cycle_id,
                "idle_tick": idle_tick,
                "focus": [c.kind for c in state.active_focus],
                "tensions": [t.kind for t in state.tensions],
                "last_action": state.last_action,
                "last_outcome": state.last_outcome,
            },
        ))
        events.append((
            "state_updated",
            {
                "cycle_id": state.cycle_id,
                "regulation": state.regulation,
                "continuity_summary": state.continuity_field.summary,
                "cognitive_mode": state.cognitive_mode,
                "risk_appetite": state.risk_appetite,
            },
        ))
        return events
