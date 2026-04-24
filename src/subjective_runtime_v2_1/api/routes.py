from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import pty
import os
import fcntl

from subjective_runtime_v2_1.api.schemas import ApprovalDecision, InputRequest, RunCreateRequest, RunConfigModel
from subjective_runtime_v2_1.runtime.events import RuntimeEvent
from subjective_runtime_v2_1.runtime.supervisor import RunConfig

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def build_router(runtime_factory, scheduler, db, events, registry=None):
    router = APIRouter()

    @router.get('/llm/status')
    async def get_llm_status():
        if not OLLAMA_AVAILABLE:
            return {'available': False, 'status': 'Ollama package not installed'}
        try:
            ollama.list()
            return {'available': True, 'status': 'Connected to Ollama'}
        except Exception as e:
            return {'available': False, 'status': f'Ollama service unreachable: {str(e)}'}

    @router.post('/runs')
    async def create_run(req: RunCreateRequest):
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        cfg = RunConfig(**req.config.model_dump())
        # If a goal was provided, inject it as the first input so the runtime
        # initialises active_goal on the first cycle.
        initial_inputs = dict(req.inputs)
        if req.goal is not None:
            initial_inputs['_goal'] = req.goal.model_dump()
        await scheduler.create_run(run_id, cfg, initial_inputs if initial_inputs else None)
        state = db.load_state(run_id)
        return {
            'run_id': run_id,
            'status': 'running',
            'cycle_id': state.cycle_id if state else 0,
        }

    @router.get('/runs')
    async def list_runs():
        return {'runs': [asdict(r) for r in db.list_runs()]}

    @router.get('/runs/{run_id}')
    async def get_run(run_id: str):
        meta = db.get_run(run_id)
        if meta is None:
            raise HTTPException(status_code=404, detail='run not found')
        return asdict(meta)

    @router.get('/runs/{run_id}/state')
    async def get_state(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        return asdict(state)

    @router.get('/runs/{run_id}/goal')
    async def get_goal(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        if state.active_goal is None:
            return {'goal': None}
        return {'goal': asdict(state.active_goal)}

    @router.get('/runs/{run_id}/plan')
    async def get_plan(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        if state.active_plan is None:
            return {'plan': None}
        return {'plan': asdict(state.active_plan)}

    @router.get('/runs/{run_id}/artifacts')
    async def list_artifacts(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        return {'artifacts': [asdict(a) for a in state.artifacts]}

    @router.get('/runs/{run_id}/summary')
    async def get_summary(run_id: str):
        meta = db.get_run(run_id)
        if meta is None:
            raise HTTPException(status_code=404, detail='run not found')
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        return {
            'run_id': run_id,
            'status': meta.status,
            'cycle_id': state.cycle_id,
            'stop_reason': state.stop_reason,
            'run_outcome': state.run_outcome,
            'total_actions': state.total_actions,
            'last_meaningful_action_ts': state.last_meaningful_action_ts,
            'goal': asdict(state.active_goal) if state.active_goal else None,
            'plan_status': state.active_plan.status if state.active_plan else None,
            'plan_current_step': state.active_plan.current_step if state.active_plan else None,
            'artifact_count': len(state.artifacts),
            'pending_approvals': [
                r for r in state.approval_requests if r.get('status') == 'pending'
            ],
        }

    @router.get('/approvals/pending')
    async def list_pending_approvals():
        """List all pending approval requests across all runs."""
        pending = []
        for meta in db.list_runs():
            state = db.load_state(meta.run_id)
            if state is None:
                continue
            for req in state.approval_requests:
                if req.get('status') == 'pending':
                    pending.append({**req, 'run_id': meta.run_id})
        return {'pending': pending}

    @router.post('/runs/{run_id}/input')
    async def enqueue_input(run_id: str, req: InputRequest):
        supervisor = scheduler.get(run_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail='run not found')
        await supervisor.inject_input(req.inputs)
        return {'run_id': run_id, 'status': 'queued'}

    @router.post('/runs/{run_id}/pause')
    async def pause_run(run_id: str):
        supervisor = scheduler.get(run_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail='run not found')
        await supervisor.pause()
        return {'run_id': run_id, 'status': 'paused'}

    @router.post('/runs/{run_id}/resume')
    async def resume_run(run_id: str):
        supervisor = scheduler.get(run_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail='run not found')
        await supervisor.resume()
        return {'run_id': run_id, 'status': 'running'}

    @router.delete('/runs/{run_id}')
    async def stop_run(run_id: str):
        await scheduler.stop_run(run_id)
        return {'run_id': run_id, 'status': 'stopped'}

    @router.get('/runs/{run_id}/events')
    async def stream_events(run_id: str, request: Request, after_seq: int = 0):
        if db.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail='run not found')

        async def event_generator():
            backlog = db.load_events(run_id, after_seq=after_seq)
            for item in backlog:
                event = RuntimeEvent(
                    run_id=item['run_id'],
                    seq=item['seq'],
                    type=item['type'],
                    payload=item['payload'],
                    created_at=item['created_at'],
                )
                yield events.live_bus.encode_sse(event)

            q = events.live_bus.subscribe_queue(run_id)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield events.live_bus.encode_sse(event)
                    except asyncio.TimeoutError:
                        yield ': keepalive\n\n'
            finally:
                events.live_bus.unsubscribe_queue(run_id, q)

        return StreamingResponse(event_generator(), media_type='text/event-stream')

    @router.post('/runs/{run_id}/approve')
    async def approve_action(run_id: str, req: ApprovalDecision):
        supervisor = scheduler.get(run_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail='run not found')
        # Resume plan if it was blocked waiting for approval
        state = db.load_state(run_id)
        if state and state.active_plan and state.active_plan.status == 'blocked':
            state.active_plan.status = 'active'
            state.stop_reason = None
            db.save_state(run_id, state)
            supervisor.runtime.state_store.save(run_id, state)
        ok = await supervisor.approve_action(req.action_id)
        if not ok:
            raise HTTPException(status_code=404, detail='pending approval request not found')
        return {'run_id': run_id, 'action_id': req.action_id, 'status': 'approved'}

    @router.post('/runs/{run_id}/deny')
    async def deny_action(run_id: str, req: ApprovalDecision):
        supervisor = scheduler.get(run_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail='run not found')
        ok = await supervisor.deny_action(req.action_id)
        if not ok:
            raise HTTPException(status_code=404, detail='pending approval request not found')
        # Mark plan failed/blocked on denial
        state = db.load_state(run_id)
        if state and state.active_plan and state.active_plan.status == 'blocked':
            state.active_plan.status = 'failed'
            state.stop_reason = 'blocked'
            state.run_outcome = {'stop_reason': 'blocked', 'reason': 'approval_denied'}
            db.save_state(run_id, state)
        return {'run_id': run_id, 'action_id': req.action_id, 'status': 'denied'}

    @router.get('/runtime/tools')
    async def list_tools():
        if registry is None:
            return {'tools': []}
        return {'tools': [{'name': t.name, 'description': t.description} for t in registry.tools.values()]}

    @router.get('/runtime/config-defaults')
    async def get_config_defaults():
        return RunConfigModel().model_dump()

    @router.get('/runs/{run_id}/events/recent')
    async def get_recent_events(run_id: str, limit: int = 200):
        if db.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail='run not found')
        events_list = db.load_events(run_id)
        return {'events': events_list[-limit:]}

    @router.get('/runs/{run_id}/state/compact')
    async def get_compact_state(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        return {
            'run_id': run_id,
            'cycle_id': state.cycle_id,
            'active_focus': state.active_focus,
            'working_memory': state.working_memory,
            'hypotheses': state.hypotheses,
            'tensions': state.tensions,
            'conflict_field': state.conflict_field,
            'continuity_field': state.continuity_field,
            'pre_narrative': state.pre_narrative,
            'post_narrative': state.post_narrative,
            'interpretive_bias': state.interpretive_bias,
            'pending_options': state.pending_options,
            'last_action': asdict(state.last_action) if getattr(state, 'last_action', None) else None,
            'last_outcome': asdict(state.last_outcome) if getattr(state, 'last_outcome', None) else None,
            'world_model': state.world_model,
            'self_model': getattr(state, 'self_model', None),
            'regulation': {
                'uncertainty_load': state.regulation.get('uncertainty_load', 0.0),
                'continuity_health': state.regulation.get('continuity_health', 1.0),
                'goal_drift': state.regulation.get('goal_drift', 0.0),
                'overload_pressure': state.regulation.get('overload_pressure', 0.0),
            }
        }

    @router.websocket('/terminal')
    async def terminal_endpoint(websocket: WebSocket):
        if os.getenv("ALLOW_DEV_TERMINAL") != "1":
            await websocket.close(code=1008, reason="Terminal access disabled by default for security.")
            return

        await websocket.accept()
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            os.execvp("bash", ["bash", "-i"])
        
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        loop = asyncio.get_running_loop()
        
        def pty_reader():
            try:
                data = os.read(fd, 4096)
                if data:
                    asyncio.run_coroutine_threadsafe(websocket.send_text(data.decode('utf-8', errors='replace')), loop)
            except BlockingIOError:
                pass
            except OSError:
                loop.remove_reader(fd)
                
        loop.add_reader(fd, pty_reader)
        
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    os.write(fd, data.encode('utf-8'))
                except OSError:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            loop.remove_reader(fd)
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except OSError:
                pass

    return router
