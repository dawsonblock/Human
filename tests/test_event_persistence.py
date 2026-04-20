import asyncio

from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


def test_event_persistence_and_backlog(tmp_path):
    db = SQLiteRunStore(tmp_path / 'events.db')
    db.create_run('r1', config={}, status='running')
    manager = EventManager(db, LiveEventBus())

    asyncio.run(manager.publish('r1', 'run_started', {'x': 1}))
    asyncio.run(manager.publish('r1', 'cycle_completed', {'cycle_id': 1}))

    backlog = db.load_events('r1')
    assert [e['seq'] for e in backlog] == [1, 2]
    assert backlog[0]['type'] == 'run_started'
    assert backlog[1]['type'] == 'cycle_completed'
