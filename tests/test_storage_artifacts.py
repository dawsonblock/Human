"""Tests for artifact indexing in run_artifacts table."""
from __future__ import annotations

import time

import pytest

from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft


def _artifact_dict(artifact_id: str, title: str = "Test Artifact") -> dict:
    return {
        "id": artifact_id,
        "type": "note",
        "title": title,
        "content": {"text": f"content of {artifact_id}"},
        "provenance": {"step_id": "s1"},
        "created_at": time.time(),
        "step_id": "s1",
    }


class _FakeArtifact:
    """Minimal artifact stand-in (no dataclass, plain object with __dataclass_fields__)."""
    def __init__(self, d: dict):
        self.__dict__.update(d)

    # Make hasattr(a, '__dataclass_fields__') return False so dict path is taken
    # by the mirroring code.


def _make_transition(run_id: str, artifacts: list[dict]) -> CycleTransition:
    state = AgentStateV2_1(cycle_id=1)
    state.artifacts = artifacts  # type: ignore[assignment]
    return CycleTransition(
        run_id=run_id,
        cycle_id=1,
        state=state,
        events=[RuntimeEventDraft(type="cycle_tick", payload={})],
        status_override=None,
    )


def test_artifacts_persisted_to_index(tmp_path):
    db = SQLiteBackend(tmp_path / "art.db")
    db.create_run("r1", config={})

    art = _artifact_dict("art-001", "My Note")
    db.apply_cycle_transition(_make_transition("r1", [art]))

    listed = db.list_artifacts("r1")
    assert len(listed) == 1
    assert listed[0]["id"] == "art-001"
    assert listed[0]["title"] == "My Note"


def test_artifacts_survive_restart(tmp_path):
    db_path = tmp_path / "restart.db"
    db1 = SQLiteBackend(db_path)
    db1.create_run("r2", config={})
    db1.apply_cycle_transition(_make_transition("r2", [_artifact_dict("art-002")]))

    # Reopen
    db2 = SQLiteBackend(db_path)
    listed = db2.list_artifacts("r2")
    assert any(a["id"] == "art-002" for a in listed)


def test_duplicate_commits_do_not_duplicate_artifacts(tmp_path):
    db = SQLiteBackend(tmp_path / "dup.db")
    db.create_run("r3", config={})

    art = _artifact_dict("art-003")
    # Commit the same artifact twice (e.g. after a retry)
    db.apply_cycle_transition(_make_transition("r3", [art]))
    db.apply_cycle_transition(_make_transition("r3", [art]))

    listed = db.list_artifacts("r3")
    ids = [a["id"] for a in listed]
    assert ids.count("art-003") == 1, f"Artifact duplicated: {ids}"


def test_multiple_artifacts_all_indexed(tmp_path):
    db = SQLiteBackend(tmp_path / "multi.db")
    db.create_run("r4", config={})

    arts = [_artifact_dict(f"art-{i:03d}", f"Artifact {i}") for i in range(5)]
    db.apply_cycle_transition(_make_transition("r4", arts))

    listed = db.list_artifacts("r4")
    assert len(listed) == 5


def test_older_state_only_artifacts_still_render(tmp_path):
    """When run_artifacts table is empty, list_artifacts falls back to state blob."""
    db = SQLiteBackend(tmp_path / "fallback.db")
    db.create_run("r5", config={})

    # Save state with artifacts directly (bypassing transition / mirroring)
    state = AgentStateV2_1(cycle_id=1)
    state.artifacts = []  # type: ignore[assignment]
    db.save_state("r5", state)

    # run_artifacts is empty but list_artifacts should not error
    listed = db.list_artifacts("r5")
    assert isinstance(listed, list)


def test_artifact_listing_merges_index_and_blob(tmp_path):
    """Verify that list_artifacts merges index rows and state blob artifacts."""
    db = SQLiteBackend(tmp_path / "merge.db")
    db.create_run("r6", config={})

    # 1. Manually insert one artifact into state blob only
    art_blob = _artifact_dict("art-blob", "Blob Only")
    state = AgentStateV2_1(cycle_id=1)
    state.artifacts = [art_blob]  # type: ignore
    db.save_state("r6", state)

    # 2. Insert another artifact via normal transition (goes to index + blob)
    art_indexed = _artifact_dict("art-idx", "Indexed")
    # We need to make sure we don't overwrite the blob-only one if we were using a real cycle
    # but here we just want to test the MERGE logic of list_artifacts.
    # So we'll manually insert into index.
    with db._conn() as conn:
        db._mirror_artifacts_tx(conn, "r6", AgentStateV2_1(artifacts=[art_indexed]))
        conn.commit()

    listed = db.list_artifacts("r6")
    ids = [a["id"] for a in listed]
    assert "art-blob" in ids
    assert "art-idx" in ids
    assert len(listed) == 2
