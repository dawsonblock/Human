# subjective_runtime_v2_1 scaffold — phase 2

This scaffold now includes a real second phase:

- SQLite-backed run state snapshots
- append-only durable event log
- live event fan-out for SSE
- run supervisors with pause/resume/stop and idle ticks
- a scheduler that can recover running or paused runs from persistence
- a FastAPI transport layer for creating runs, enqueueing input, listing state, and streaming events

What it still is not:

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

## Core transport endpoints

- `POST /runs`
- `GET /runs`
- `GET /runs/{run_id}/state`
- `POST /runs/{run_id}/input`
- `POST /runs/{run_id}/pause`
- `POST /runs/{run_id}/resume`
- `DELETE /runs/{run_id}`
- `GET /runs/{run_id}/events`

The authoritative long-lived state is still a snapshot plus event-log scaffold. The event log is intended to become the canonical causal record as the system matures.


## Phase 3 additions

This scaffold now includes homeostatic regulation, explore/exploit mode switching, hypothesis generation, bounded associative synthesis, and idle-time consolidation. These additions make the runtime more adaptive under stress, more exploratory when stable, and better at turning discrepancies into explanations. They do not imply consciousness or sentience.
