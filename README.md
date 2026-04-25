# Human Runtime

> A bounded, auditable local cognitive runtime with an operator dashboard and optional LLM-powered planning via Ollama.

---

## What is this?

**Human Runtime** is a local AI execution environment built for operators who want visibility and control over everything an agent does.

It is **not** a chat app. It is an operator cockpit — you define goals, the system builds a plan, executes it step-by-step, and shows you everything in real time. You can pause, resume, approve, or deny any action at any point.

The execution model is deterministic by default. With [Ollama](https://ollama.com) installed, you unlock **Dynamic LLM Planning**: write any goal in plain English and let `llama3.2` generate the execution plan.

---

## Features

| Capability | Status |
|---|---|
| Operator goal → bounded linear plan | ✅ |
| Dynamic LLM planning via Ollama (`llama3.2`) | ✅ |
| Real-time event stream (SSE) | ✅ |
| React + Vite operator dashboard | ✅ |
| Pause / Resume / Stop controls | ✅ |
| Operator approval gate for sensitive actions | ✅ |
| Artifact browser | ✅ |
| Cognitive Graph visualizer | ✅ |
| SQLite persistence (state, events, artifacts) | ✅ |
| Crash recovery (resume paused/running runs after restart) | ✅ |
| File read, write, preview, search | ✅ |
| Shell execution | ❌ Disabled by default |
| SaaS integrations / browser automation | ❌ Out of scope |
| Production hardening / deployment | ❌ Not claimed |

---

## Quickstart

```bash
# 1. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Build the frontend
cd frontend
npm install
npm run build
cd ..

# 3. Run the test suite (148 tests)
pytest

# 4. Start the server
uvicorn subjective_runtime_v2_1.api.app:app --reload
# → Open http://localhost:8000
```

### Enable LLM Planning (optional but recommended)

```bash
# Install Ollama
brew install ollama        # macOS
ollama serve               # Start the server
ollama pull llama3.2       # Pull the model (~2GB)
```

Once running, the dashboard will show a **LLM Ready** indicator. Select **Dynamic LLM Plan** in the Goal Composer and write any goal in plain English.

---

## Goal Types

| Mode | What it does |
|---|---|
| `dynamic_llm` | Sends your goal to `llama3.2`. The LLM generates the step-by-step plan. Works with any natural language goal. |
| `operator_request` | Generic: echoes the goal and records it to memory |
| `inspect_workspace` | Lists the allowed workspace directory |
| `summarize_files` | Lists files and writes a summary note |
| `extract_facts` | Lists files and records extraction intent to episodic memory |
| `draft_note` | Appends a draft to `draft.md` in the workspace |
| `propose_write` | Stages a write preview, then requires operator approval before writing |

---

## Dashboard

Start the dev server for the UI:

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

| Panel | Purpose |
|---|---|
| **Left sidebar** | Run browser — list, search, and select cognitive threads |
| **Center — Timeline** | Live SSE event feed. Click any event to inspect its full JSON payload |
| **Center — Graph** | Cognitive state visualizer (goals, plans, tensions, focus candidates) |
| **Center — Help** | Step-by-step usage guide built into the UI |
| **Right — Inspector** | Internal state: hypotheses, working memory, self-model fields |
| **Right — Approvals** | Operator approval queue for gated tool calls |
| **Right — Artifacts** | Clickable list of all artifacts produced by the selected run |

---

## API Reference

All endpoints are prefixed with `/api`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Serves the React dashboard |
| `POST` | `/api/runs` | Create a run (with optional goal) |
| `GET` | `/api/runs` | List all runs |
| `GET` | `/api/runs/{id}/summary` | Compact run status, progress, approvals |
| `GET` | `/api/runs/{id}/plan` | Active plan with step statuses |
| `GET` | `/api/runs/{id}/state/compact` | Cognitive state + regulation health |
| `GET` | `/api/runs/{id}/artifacts` | Artifacts produced by this run |
| `GET` | `/api/runs/{id}/events` | SSE stream of all events |
| `POST` | `/api/runs/{id}/pause` | Pause execution |
| `POST` | `/api/runs/{id}/resume` | Resume execution |
| `DELETE` | `/api/runs/{id}` | Stop and clean up |
| `POST` | `/api/runs/{id}/approve` | Approve a pending gated action |
| `POST` | `/api/runs/{id}/deny` | Deny a pending gated action |
| `GET` | `/api/approvals/pending` | All pending approvals across runs |
| `GET` | `/api/llm/status` | Ollama health check |

---

## Safety Model

- All file operations are bounded by `allowed_roots` (default: `.`)
- `file_write` requires explicit operator approval before execution
- `write_file_preview` stages content for review without writing
- Risky tools are gated by `ActionGate` pre-execution
- **No shell execution.** The `pty.fork()` terminal is disabled by default. It can only be re-enabled in development with `ALLOW_DEV_TERMINAL=1` — do not set this in any shared or networked environment.
- No network access, no process spawning, no unconstrained automation

---

## Execution Authority Path

```
operator input
  → input_queue
  → RunSupervisor (_cycle_lock)
    → RuntimeCore.cycle()          # pure, no side effects
    → CycleTransition              # goal / plan / artifact / event drafts
    → SQLiteRunStore.apply()       # atomic write (state + events)
    → EventManager.publish()       # live SSE fan-out to subscribers
```

---

## Project Structure

```
Human-main/
├── src/subjective_runtime_v2_1/
│   ├── api/              # FastAPI routes + SSE + schemas
│   ├── runtime/          # Supervisor, core loop, scheduler, events
│   ├── planning/         # Goal planner (deterministic + LLM hybrid)
│   ├── action/           # Tool registry, gate, executor, approvals
│   ├── state/            # SQLite store, state models
│   ├── engines/          # Homeostasis, hypothesis, narrative, conflict
│   ├── memory/           # Working, episodic, semantic, procedural
│   ├── tension/          # Tension detection engine
│   └── self_model/       # Drift tracking, self-model
├── frontend/             # React + Vite + Tailwind operator dashboard
└── tests/                # 148 tests
```

---

## License

MIT
