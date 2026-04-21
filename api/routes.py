from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from subjective_runtime_v2_1.api.schemas import ApprovalDecision, InputRequest, RunCreateRequest
from subjective_runtime_v2_1.runtime.events import RuntimeEvent
from subjective_runtime_v2_1.runtime.supervisor import RunConfig


def build_router(runtime_factory, scheduler, db, events):
    router = APIRouter()

    @router.post('/runs')
    async def create_run(req: RunCreateRequest):
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        cfg = RunConfig(**req.config.model_dump())
        await scheduler.create_run(run_id, cfg, req.inputs)
        state = db.load_state(run_id)
        return {
            'run_id': run_id,
            'status': 'running',
            'cycle_id': state.cycle_id if state else 0,
        }

    @router.get('/runs')
    async def list_runs():
        return {'runs': [asdict(r) for r in db.list_runs()]}

    @router.get('/runs/{run_id}/state')
    async def get_state(run_id: str):
        state = db.load_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail='run not found')
        return asdict(state)

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
        return {'run_id': run_id, 'action_id': req.action_id, 'status': 'denied'}

    return router
