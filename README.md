# subjective_runtime_v2_1

A bounded, auditable local assistant runtime with a modern React web UI.

One supervisor-owned execution loop, one persisted run/event model, one bounded tool surface, one approval flow, one operator-facing interface.

## What it can do now

- Accept operator goals and execute them as bounded, linear plans
- Inspect a folder (list directory)
- Read files within allowed roots
- Search files with regex patterns
- Append notes / drafts to files
- Stage file writes as previews for operator approval
- Apply approved writes
- Show live progress via SSE and a built-in React web UI dashboard
- Pause, resume, and stop runs
- Recover paused/running runs after restart
- Persist all state, events, approvals, and artifacts to SQLite
- Stream all events to live subscribers (SSE)

## What it does not do

- **No shell execution** (Terminal access is completely disabled by default for security. It can only be enabled in development with `ALLOW_DEV_TERMINAL=1`)
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

# Build the frontend UI
cd frontend
npm install
npm run build
cd ..

# Run tests
pytest                      # All tests pass

# Start the server
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

## API endpoints (Prefixed with `/api`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Web UI (served at root) |
| POST | `/api/runs` | Create a new run (with optional goal) |
| GET | `/api/runs` | List all runs |
| GET | `/api/runs/{run_id}` | Run metadata |
| GET | `/api/runs/{run_id}/state` | Full state snapshot |
| GET | `/api/runs/{run_id}/goal` | Current active goal |
| GET | `/api/runs/{run_id}/plan` | Current active plan with step statuses |
| GET | `/api/runs/{run_id}/artifacts` | Artifacts produced by this run |
| GET | `/api/runs/{run_id}/summary` | Compact run summary (status, progress, approvals) |
| GET | `/api/runs/{run_id}/state/compact` | Compact run state and regulation health |
| POST | `/api/runs/{run_id}/input` | Enqueue external input |
| POST | `/api/runs/{run_id}/pause` | Pause execution |
| POST | `/api/runs/{run_id}/resume` | Resume execution |
| DELETE | `/api/runs/{run_id}` | Stop and clean up |
| GET | `/api/runs/{run_id}/events` | SSE stream of all events |
| POST | `/api/runs/{run_id}/approve` | Approve a pending action |
| POST | `/api/runs/{run_id}/deny` | Deny a pending action |
| GET | `/api/approvals/pending` | List pending approvals across all runs |

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
4. Operator approves via `POST /api/runs/{run_id}/approve` or the UI
5. The approval re-queues the action; the next cycle executes it exactly once
6. On denial: the plan is marked failed, `stop_reason=blocked`

## Authority path

```
operator input → input_queue → RunSupervisor (_cycle_lock)
  → RuntimeCore.cycle() [pure, no side effects]
  → CycleTransition [goal/plan/artifact/event drafts]
  → SQLiteRunStore.apply_cycle_transition() [atomic state+events]
  → EventManager.publish_persisted_batch() [live SSE fan-out]
```

## Package layout

The codebase is organized in a standard Python package layout under `src/subjective_runtime_v2_1/`.
All top-level directories (`action/`, `runtime/`, `state/`, `api/`, etc.) are sub-packages.
Install with `pip install -e ".[dev]"`.
