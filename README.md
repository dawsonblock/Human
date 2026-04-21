# subjective_runtime_v2_1

A bounded, auditable local assistant runtime with a web UI.

One supervisor-owned execution loop, one persisted run/event model, one bounded tool surface, one approval flow, one operator-facing interface.

## What it can do now

- Accept operator goals and execute them as bounded, linear plans
- Inspect a folder (list directory)
- Read files within allowed roots
- Search files with regex patterns
- Append notes / drafts to files
- Stage file writes as previews for operator approval
- Apply approved writes
- Show live progress via SSE and a built-in web UI
- Pause, resume, and stop runs
- Recover paused/running runs after restart
- Persist all state, events, approvals, and artifacts to SQLite
- Stream all events to live subscribers (SSE)

## What it does not do

- No shell execution
- No unconstrained browser automation
- No SaaS connectors
- No multi-agent orchestration
- No LLM integration (heuristic planner only)
- No production hardening, sandboxing, or deployment proof
- No claim of production readiness

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # 143 tests pass
uvicorn subjective_runtime_v2_1.api.app:app --reload
# Open http://localhost:8000
```

## Supported goal types

| Type | What happens |
|------|--------------|
| `inspect_workspace` | Lists the allowed workspace directory |
| `summarize_files` | Lists files and writes a summary note |
| `extract_facts` | Lists files and records extraction intent to memory |
| `draft_note` | Appends a draft to `draft.md` in the workspace |
| `propose_write` | Stages a write preview, then gates on operator approval before writing |
| `operator_request` | Generic: echo + memory_write acknowledging the goal |

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Web UI |
| POST | `/runs` | Create a new run (with optional goal) |
| GET | `/runs` | List all runs |
| GET | `/runs/{run_id}` | Run metadata |
| GET | `/runs/{run_id}/state` | Full state snapshot |
| GET | `/runs/{run_id}/goal` | Current active goal |
| GET | `/runs/{run_id}/plan` | Current active plan with step statuses |
| GET | `/runs/{run_id}/artifacts` | Artifacts produced by this run |
| GET | `/runs/{run_id}/summary` | Compact run summary (status, progress, approvals) |
| POST | `/runs/{run_id}/input` | Enqueue external input |
| POST | `/runs/{run_id}/pause` | Pause execution |
| POST | `/runs/{run_id}/resume` | Resume execution |
| DELETE | `/runs/{run_id}` | Stop and clean up |
| GET | `/runs/{run_id}/events` | SSE stream of all events |
| POST | `/runs/{run_id}/approve` | Approve a pending action |
| POST | `/runs/{run_id}/deny` | Deny a pending action |
| GET | `/approvals/pending` | List pending approvals across all runs |

## Creating a run with a goal

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": {"type": "inspect_workspace", "description": "List my project folder"},
    "config": {"max_actions": 10}
  }'
```

## Safety boundaries

- All file operations are bounded by `allowed_roots` (default: `.`)
- `file_write` requires operator approval (`requires_confirmation=True`)
- `write_file_preview` stages a preview without writing — shows existing vs proposed content
- Risky tools are gated by `ActionGate` before execution
- No shell execution, no process spawning, no network access

## Approval flow

When the planner selects a tool marked `requires_confirmation=True` (e.g. `file_write`):
1. An approval request is created in state (status=`pending`) and persisted
2. A `approval_requested` event is emitted
3. The run pauses at that step (`plan.status=blocked`)
4. Operator approves via `POST /runs/{run_id}/approve` or the UI
5. The approval re-queues the action; the next cycle executes it exactly once
6. On denial: the plan is marked failed, `stop_reason=blocked`

## Recovery

On restart, `scheduler.recover_runs()` loads all `running` or `paused` runs from SQLite:
- Running runs restart their loop
- Paused runs restore in a paused state, awaiting `resume()`

## Persistence

Everything is stored in SQLite (`runtime.db` by default):
- `runs`: run metadata, status, and full state JSON
- `run_events`: append-only event log with per-run sequence numbers

A run can be fully reconstructed from its persisted events alone.

## Authority path

```
operator input → input_queue → RunSupervisor (_cycle_lock)
  → RuntimeCore.cycle() [pure, no side effects]
  → CycleTransition [goal/plan/artifact/event drafts]
  → SQLiteRunStore.apply_cycle_transition() [atomic state+events]
  → EventManager.publish_persisted_batch() [live SSE fan-out]
```

Lifecycle events (pause, resume, stop) go through `EventManager.publish()` directly.

## Package layout

The `src/subjective_runtime_v2_1` directory is a relative symlink to the repo root.
All top-level directories (`action/`, `runtime/`, `state/`, `api/`, etc.) are sub-packages.
Install with `pip install -e ".[dev]"`.

## Next steps (not yet built)

1. Replace the heuristic planner with an optional bounded LLM planner
2. Add proper http_get with domain allowlist, timeout, and size limits
3. Add multi-step fact extraction with citation provenance
4. Add artifact diffing and versioning
5. Replace the symlink layout with a proper `src/` package tree

