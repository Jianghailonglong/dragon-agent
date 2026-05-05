import pytest
from pathlib import Path

from session.session import Session
from session.manager import SessionManager
from resilience.checkpoint import CheckpointManager


@pytest.fixture
def checkpoint_mgr(tmp_path):
    mgr = SessionManager(storage_dir=str(tmp_path))
    return CheckpointManager(mgr), mgr


def test_begin_and_commit_turn(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr
    session = mgr.get_or_create("s1")
    session.add_message("user", "hi")
    mgr.save(session)

    cp_mgr.begin_user_turn(session)
    assert session.has_pending_user_turn()

    cp_mgr.commit_user_turn(session)
    assert not session.has_pending_user_turn()
    assert session.get_runtime_checkpoint() is None


def test_save_tool_checkpoint(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr
    session = mgr.get_or_create("s1")
    mgr.save(session)

    cp_mgr.save_tool_checkpoint(session, tool_index=0, tool_name="read_file")
    cp = session.get_runtime_checkpoint()
    assert cp["last_completed_tool_index"] == 0
    assert cp["last_completed_tool_name"] == "read_file"

    cp_mgr.save_tool_checkpoint(session, tool_index=1, tool_name="exec")
    cp = session.get_runtime_checkpoint()
    assert cp["last_completed_tool_index"] == 1


def test_recover_clean_session(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr
    session = mgr.get_or_create("s1")
    session.add_message("user", "hello")
    mgr.save(session)

    recovered, status = cp_mgr.recover("s1")
    assert status == "clean"
    assert recovered is not None


def test_recover_interrupted_session(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr
    session = mgr.get_or_create("s1")
    session.add_message("user", "hello")
    session.mark_pending_user_turn()
    session.set_runtime_checkpoint({"last_completed_tool_index": 2, "last_completed_tool_name": "exec"})
    mgr.save(session)

    recovered, status = cp_mgr.recover("s1")
    assert status == "recovered"
    assert recovered is not None
    # Should have an interruption message
    last_msg = recovered.messages[-1]
    assert "interrupted" in last_msg["content"].lower()
    assert "exec" in last_msg["content"]


def test_recover_pending_no_checkpoint(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr
    session = mgr.get_or_create("s1")
    session.add_message("user", "hello")
    session.mark_pending_user_turn()
    mgr.save(session)

    recovered, status = cp_mgr.recover("s1")
    assert status == "recovered"
    last_msg = recovered.messages[-1]
    assert "interrupted" in last_msg["content"].lower()


def test_scan_for_interrupted(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr

    s1 = mgr.get_or_create("clean")
    s1.add_message("user", "hi")
    mgr.save(s1)

    s2 = mgr.get_or_create("interrupted")
    s2.add_message("user", "hi")
    s2.mark_pending_user_turn()
    mgr.save(s2)

    interrupted = cp_mgr.scan_for_interrupted()
    assert interrupted == ["interrupted"]


def test_recover_all(checkpoint_mgr):
    cp_mgr, mgr = checkpoint_mgr

    s1 = mgr.get_or_create("s1")
    s1.mark_pending_user_turn()
    mgr.save(s1)

    s2 = mgr.get_or_create("s2")
    s2.mark_pending_user_turn()
    mgr.save(s2)

    results = cp_mgr.recover_all()
    assert "s1" in results
    assert "s2" in results
    assert all(v == "recovered" for v in results.values())
