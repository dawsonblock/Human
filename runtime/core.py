from __future__ import annotations

from dataclasses import asdict
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
from subjective_runtime_v2_1.planning.goal_planner import build_plan_for_goal
from subjective_runtime_v2_1.planning.planner import Planner
from subjective_runtime_v2_1.planning.scoring import score_action
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft
from subjective_runtime_v2_1.state.models import (
    ActionOption,
    AgentStateV2_1,
    Artifact,
    Candidate,
    Goal,
    Plan,
    RawObservation,
    Tension,
)
from subjective_runtime_v2_1.state.store import InMemoryStateStore
from subjective_runtime_v2_1.tension.engine import TensionEngine
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts
from subjective_runtime_v2_1.workspace.attention import AttentionGate
from subjective_runtime_v2_1.workspace.workspace import Workspace

WORKING_MEMORY_CAP = 12  # max items; older entries are evicted to keep the buffer compact

# Defaults used when reconstructing an ActionOption from a stored approval request.
# These scores do not affect gate logic (the gate is bypassed for approved actions);
# they exist only to satisfy the ActionOption dataclass.
_APPROVAL_EXEC_EXPECTED_VALUE: float = 0.9
_APPROVAL_EXEC_ESTIMATED_COST: float = 0.0
_APPROVAL_EXEC_ESTIMATED_RISK: float = 0.0

# Backward-compat alias so existing imports of CycleResult continue to work.
CycleResult = CycleTransition


class RuntimeCore:
    def __init__(
        self,
        state_store: InMemoryStateStore,
        gate: ActionGate,
        executor: Executor,
        config: RuntimeConfig | None = None,
        allowed_roots: list[str] | None = None,
    ) -> None:
        self.state_store = state_store
        self.config = config or RuntimeConfig()
        self.allowed_roots = allowed_roots or ['.']
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

    def cycle(
        self,
        run_id: str,
        inputs: dict,
        idle_tick: bool = False,
        max_cycles: int = 0,
        max_actions: int = 0,
        max_replans: int = 3,
    ) -> CycleTransition:
        """Run one cognitive cycle and return a CycleTransition.

        RuntimeCore does NOT persist the resulting state; that is the caller's
        responsibility.  The only exception is the internal InMemoryStateStore
        used as a cycle-to-cycle buffer — that save is done here so that
        successive direct calls (e.g. in unit tests) see a consistent state.
        """
        state = self.state_store.load(run_id)
        state.cycle_id += 1
        state.timestamp = now_ts()

        # ---- goal initialization from operator input ----
        if "_goal" in inputs and state.active_goal is None:
            goal_data = inputs["_goal"]
            state.active_goal = Goal(
                id=new_id("goal"),
                type=goal_data.get("type", "operator_request"),
                description=goal_data.get("description", ""),
                priority=goal_data.get("priority", 0.5),
                success_criteria=goal_data.get("success_criteria", ""),
                created_at=state.timestamp,
            )

        # ---- build plan when goal exists but no plan yet ----
        plan_events: list[RuntimeEventDraft] = []
        if state.active_goal is not None and state.active_plan is None and state.active_goal.status == "active":
            state.active_plan = build_plan_for_goal(state.active_goal, self.allowed_roots)
            plan_events.append(RuntimeEventDraft(
                type="plan_created",
                payload={
                    "goal_id": state.active_goal.id,
                    "plan_id": state.active_plan.id,
                    "steps": [asdict(s) for s in state.active_plan.steps],
                },
            ))

        # ---- ceiling checks ----
        ceiling_stop: str | None = None
        if max_cycles > 0 and state.cycle_id >= max_cycles:
            ceiling_stop = "completed"
        if max_actions > 0 and state.total_actions >= max_actions:
            ceiling_stop = "completed"

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
        chosen = None
        step_events: list[RuntimeEventDraft] = []

        approval_id = inputs.get("_approval_granted") if inputs else None
        matched_approved = False
        if approval_id:
            # Execute a previously approved action exactly once.
            # The request status transitions: pending → approved (by supervisor) → executed (here).
            for req in state.approval_requests:
                if req.get("action_id") == approval_id and req.get("status") == "approved":
                    matched_approved = True
                    chosen = ActionOption(
                        id=req["action_id"],
                        name=req.get("reason", req.get("tool_name", "approved_action")),
                        target={"tool_name": req["tool_name"], "arguments": req.get("arguments", {})},
                        predicted_world_effect={},
                        predicted_self_effect={},
                        expected_value=_APPROVAL_EXEC_EXPECTED_VALUE,
                        estimated_cost=_APPROVAL_EXEC_ESTIMATED_COST,
                        estimated_risk=_APPROVAL_EXEC_ESTIMATED_RISK,
                    )
                    state.last_action = {"id": chosen.id, "name": chosen.name, "gate_reason": "approval_granted"}
                    ctx = ExecutionContext(
                        run_id=run_id,
                        cycle_id=state.cycle_id,
                        idle_tick=idle_tick,
                        policies={},
                        self_model=state.self_model,
                        world_model=state.world_model,
                        regulation=state.regulation,
                        working_memory=list(state.working_memory),
                        goal_stack=list(state.goal_stack),
                    )
                    outcome = self.executor.execute(chosen, ctx)
                    state.last_outcome = outcome
                    tool_record = dict(outcome)
                    self._apply_tool_mutations(state, outcome)
                    self._collect_artifacts(state, run_id, outcome, req.get("step_id"))
                    state.total_actions += 1
                    state.last_meaningful_action_ts = state.timestamp
                    # Advance plan step if this was a plan-directed action
                    step_events += self._advance_plan_step(state, chosen.id, outcome)
                    # Mark as executed so duplicate approval signals are no-ops.
                    req["status"] = "executed"
                    break

        if not matched_approved:
            # No live approved request matched (stale/duplicate signal or no signal):
            # use goal-directed step if a plan is active, otherwise heuristic planner.
            if state.active_plan and state.active_plan.status == "active":
                options = self._plan_step_options(state)
            else:
                options = self.planner.propose(state)
            state.pending_options = options
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
                        working_memory=list(state.working_memory),
                        goal_stack=list(state.goal_stack),
                    )
                    outcome = self.executor.execute(chosen, ctx)
                    state.last_outcome = outcome
                    tool_record = dict(outcome)
                    self._apply_tool_mutations(state, outcome)
                    self._collect_artifacts(state, run_id, outcome, chosen.target.get("step_id"))
                    state.total_actions += 1
                    state.last_meaningful_action_ts = state.timestamp
                    step_events += self._advance_plan_step(state, chosen.id, outcome)
                elif reason == "approval_required":
                    # Enrich approval request with plan/step context
                    step_id = chosen.target.get("step_id")
                    affected = chosen.target.get("arguments", {}).get("path")
                    req = {
                        "action_id": chosen.id,
                        "tool_name": chosen.target.get("tool_name"),
                        "arguments": chosen.target.get("arguments", {}),
                        "reason": chosen.name,
                        "created_at": state.timestamp,
                        "status": "pending",
                        "step_id": step_id,
                        "affected_resource": affected,
                        "plan_id": state.active_plan.id if state.active_plan else None,
                        "goal_id": state.active_goal.id if state.active_goal else None,
                    }
                    state.approval_requests.append(req)
                    new_approval = req
                    state.last_outcome = {"status": "blocked", "reason": reason}
                    if state.active_plan:
                        state.active_plan.status = "blocked"
                        state.stop_reason = "awaiting_approval"
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

        # ---- ceiling stop ----
        status_override: str | None = None
        if ceiling_stop and not state.stop_reason:
            state.stop_reason = ceiling_stop
            state.run_outcome = {
                "stop_reason": ceiling_stop,
                "cycle_id": state.cycle_id,
                "total_actions": state.total_actions,
            }
            status_override = "completed"
            plan_events.append(RuntimeEventDraft(
                type="run_stopped",
                payload={"reason": ceiling_stop, "cycle_id": state.cycle_id},
            ))

        # ---- persist to internal buffer (for unit-test compat) ----
        self.state_store.save(run_id, state)

        # ---- build CycleTransition ----
        event_drafts = self._build_cycle_events(state, idle_tick, tool_record, new_approval)
        event_drafts = plan_events + step_events + event_drafts
        tool_records = [tool_record] if tool_record else []

        return CycleTransition(
            run_id=run_id,
            cycle_id=state.cycle_id,
            state=state,
            events=event_drafts,
            chosen_action=chosen if tool_record is not None else None,
            approval_request=new_approval,
            status_override=status_override,
            tool_records=tool_records,
            cycle_summary={
                "cycle_id": state.cycle_id,
                "idle_tick": idle_tick,
                "cognitive_mode": state.cognitive_mode,
                "tension_count": len(state.tensions),
                "focus_kinds": [c.kind for c in state.active_focus],
                "stop_reason": state.stop_reason,
                "total_actions": state.total_actions,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _plan_step_options(self, state: AgentStateV2_1) -> list[ActionOption]:
        """Build ActionOptions from the current active plan step."""
        plan = state.active_plan
        if plan is None or plan.current_step >= len(plan.steps):
            return []
        step = plan.steps[plan.current_step]
        if step.status not in ("pending", "running"):
            return []
        option = ActionOption(
            id=new_id("act"),
            name=step.description,
            target={
                "tool_name": step.tool_name,
                "arguments": step.arguments,
                "reason": step.description,
                "step_id": step.id,
            },
            predicted_world_effect={"plan_progress": True},
            predicted_self_effect={"continuity_health": 0.02},
            expected_value=0.75,
            estimated_cost=0.05,
            estimated_risk=0.05,
            tension_reduction=0.15,
            uncertainty_reduction=0.15,
            continuity_preservation=0.20,
            valuation_alignment=0.15,
            narrative_fit=0.15,
            conflict_resolution_value=0.05,
            information_gain=0.15,
            mode_fit=0.10,
        )
        return [option]

    def _advance_plan_step(
        self, state: AgentStateV2_1, action_id: str, outcome: dict
    ) -> list[RuntimeEventDraft]:
        """Mark the current plan step complete/failed and advance the pointer."""
        events: list[RuntimeEventDraft] = []
        plan = state.active_plan
        if (
            plan is None
            or plan.status != "active"
            or plan.current_step >= len(plan.steps)
        ):
            return events

        step = plan.steps[plan.current_step]
        executed_step_id = outcome.get("step_id") or action_id
        is_current_plan_step = (
            step.status in ("pending", "running")
            and executed_step_id == step.id
        )
        if not is_current_plan_step:
            return events

        ts = now_ts()
        if outcome.get("status") == "ok":
            step.status = "completed"
            step.completed_at = ts
            step.output = outcome.get("result", {})
            events.append(RuntimeEventDraft(
                type="plan_step_completed",
                payload={
                    "plan_id": plan.id,
                    "step_id": step.id,
                    "step_index": plan.current_step,
                    "tool_name": step.tool_name,
                },
            ))
            plan.current_step += 1
            if plan.current_step >= len(plan.steps):
                plan.status = "completed"
                if state.active_goal:
                    state.active_goal.status = "completed"
                state.stop_reason = "completed"
                state.run_outcome = {
                    "stop_reason": "completed",
                    "goal_id": state.active_goal.id if state.active_goal else None,
                    "plan_id": plan.id,
                    "total_actions": state.total_actions,
                }
                events.append(RuntimeEventDraft(
                    type="goal_completed",
                    payload={
                        "goal_id": state.active_goal.id if state.active_goal else None,
                        "plan_id": plan.id,
                    },
                ))
            else:
                next_step = plan.steps[plan.current_step]
                next_step.status = "running"
                if next_step.started_at is None:
                    next_step.started_at = ts
                events.append(RuntimeEventDraft(
                    type="plan_step_started",
                    payload={
                        "plan_id": plan.id,
                        "step_id": next_step.id,
                        "step_index": plan.current_step,
                        "tool_name": next_step.tool_name,
                    },
                ))
        else:
            step.status = "failed"
            step.completed_at = ts
            step.error = outcome.get("error")
            events.append(RuntimeEventDraft(
                type="plan_step_failed",
                payload={
                    "plan_id": plan.id,
                    "step_id": step.id,
                    "step_index": plan.current_step,
                    "error": step.error,
                },
            ))
            plan.status = "failed"
            state.stop_reason = "error"
            state.run_outcome = {
                "stop_reason": "error",
                "step_id": step.id,
                "error": step.error,
            }
        return events

    def _collect_artifacts(
        self,
        state: AgentStateV2_1,
        run_id: str,
        outcome: dict,
        step_id: str | None,
    ) -> None:
        """Persist tool-produced artifacts into state.artifacts."""
        for raw in outcome.get("artifacts") or []:
            artifact = Artifact(
                id=new_id("art"),
                run_id=run_id,
                type=raw.get("type", "tool_output"),
                title=raw.get("title", f"Output from {outcome.get('tool_name', 'tool')}"),
                content=raw.get("content", {}),
                provenance={
                    "tool_name": outcome.get("tool_name"),
                    "cycle_id": state.cycle_id,
                    "step_id": step_id,
                },
                created_at=state.timestamp,
                step_id=step_id,
            )
            state.artifacts.append(artifact)

    def _apply_tool_mutations(self, state: AgentStateV2_1, outcome: dict) -> None:
        """Apply memory_writes and state_delta from tool execution to state."""
        for raw_entry in outcome.get("memory_writes") or []:
            # Ensure cycle_id is stamped on the routed record.  We build a new
            # dict rather than mutating the ToolResult entry in place.
            routed = raw_entry if "cycle_id" in raw_entry else dict(raw_entry, cycle_id=state.cycle_id)
            self.memory.apply_memory_write(state, routed)

        # Trim working_memory to its cap after all writes.
        if len(state.working_memory) > WORKING_MEMORY_CAP:
            state.working_memory = state.working_memory[-WORKING_MEMORY_CAP:]

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

        # Always promote a compact episodic recall from recent memory — provides
        # a second kind even when there are no tensions or tool outcomes, so
        # AssociativeModule has real cross-kind input.
        recent_episodic = memories.get("episodic", [])
        if recent_episodic:
            wm.append({
                "kind": "episodic_recall",
                "cycle_id": cycle_id,
                "episode_cycle_id": recent_episodic[-1].get("cycle_id"),
                "tensions": recent_episodic[-1].get("tensions", []),
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
    ) -> list[RuntimeEventDraft]:
        """Collect all cycle-scoped events as RuntimeEventDraft objects."""
        events: list[RuntimeEventDraft] = []

        if state.last_action is not None:
            events.append(RuntimeEventDraft(
                type="tool_call_proposed",
                payload={"cycle_id": state.cycle_id, "last_action": state.last_action},
            ))

        if tool_record is not None:
            event_type = "tool_call_executed" if tool_record.get("status") == "ok" else "tool_call_failed"
            events.append(RuntimeEventDraft(
                type=event_type,
                payload={
                    "cycle_id": state.cycle_id,
                    "last_action": state.last_action,
                    "last_outcome": state.last_outcome,
                },
            ))

        if new_approval is not None:
            events.append(RuntimeEventDraft(
                type="approval_requested",
                payload=dict(new_approval),
            ))

        events.append(RuntimeEventDraft(
            type="cycle_completed",
            payload={
                "cycle_id": state.cycle_id,
                "idle_tick": idle_tick,
                "focus": [c.kind for c in state.active_focus],
                "tensions": [t.kind for t in state.tensions],
                "last_action": state.last_action,
                "last_outcome": state.last_outcome,
            },
        ))
        events.append(RuntimeEventDraft(
            type="state_updated",
            payload={
                "cycle_id": state.cycle_id,
                "regulation": state.regulation,
                "continuity_summary": state.continuity_field.summary,
                "cognitive_mode": state.cognitive_mode,
                "risk_appetite": state.risk_appetite,
            },
        ))
        return events
