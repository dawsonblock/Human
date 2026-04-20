# subjective_runtime_v2_1

A credible runtime testbed for integrated, temporally extended, self-affecting cognition — Phase 3.

## What is in here

- SQLite-backed run state with **atomic state+event commits** via `apply_cycle_transition`
- Append-only durable event log with live SSE fan-out
- `RuntimeCore.cycle()` returns a pure `CycleResult`; persistence is the supervisor's responsibility
- Run supervisors with pause/resume/stop, idle ticks, and `_cycle_lock` as the single execution authority
- Scheduler that recovers running or paused runs from persistence on startup
- `memory_write` tool routes writes by kind into durable state (`working_memory`, `episodic_trace`, `self_history`)
- Homeostatic regulation, explore/exploit mode switching, hypothesis generation, bounded associative synthesis, idle-time consolidation
- Working-memory promotion: every cycle leaves a compact "what mattered" packet
- Approval flow: `POST /runs/{run_id}/approve` and `POST /runs/{run_id}/deny`

## What it is not

- not a finished cognition runtime
- not production-grade
- not a claim of consciousness or sentience
- not a final persistence/event schema

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn subjective_runtime_v2_1.api.app:app --reload
```

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/runs` | Create a new run |
| GET | `/runs` | List all runs |
| GET | `/runs/{run_id}/state` | Current state snapshot |
| POST | `/runs/{run_id}/input` | Enqueue external input |
| POST | `/runs/{run_id}/pause` | Pause execution |
| POST | `/runs/{run_id}/resume` | Resume execution |
| DELETE | `/runs/{run_id}` | Stop and clean up |
| GET | `/runs/{run_id}/events` | SSE stream of events |
| POST | `/runs/{run_id}/approve` | Approve a pending action |
| POST | `/runs/{run_id}/deny` | Deny a pending action |

## Authority path

```
input queue → supervisor (_cycle_lock) → RuntimeCore.cycle() → CycleResult
  → SQLiteRunStore.apply_cycle_transition() [atomic state+events]
  → EventManager.fan_out() [live SSE]
```

Lifecycle events (pause, resume, stop) continue to go through `EventManager.publish()`.

## What is stubbed

- `http_get` tool: network calls are not implemented
- No external language model integration
- Planner proposes echo/memory_write actions; real epistemic probes are not yet wired
- Self-model and world-model updates are heuristic, not learned

