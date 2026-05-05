import pytest
import json
from pathlib import Path

from session.session import Session
from session.manager import SessionManager


@pytest.fixture
def storage_dir(tmp_path):
    return str(tmp_path / "sessions")


def test_jsonl_save_and_load(storage_dir):
    mgr = SessionManager(storage_dir=storage_dir)
    s = mgr.get_or_create("test_key")
    s.add_message("user", "hello")
    s.add_message("assistant", "hi there")
    mgr.save(s)

    # Verify JSONL file exists
    jsonl_path = Path(storage_dir) / "test_key.jsonl"
    assert jsonl_path.exists()

    # Load from disk in a fresh manager
    mgr2 = SessionManager(storage_dir=storage_dir)
    loaded = mgr2.get("test_key")
    assert loaded is not None
    assert loaded.key == "test_key"
    assert len(loaded.messages) == 2
    assert loaded.messages[0]["content"] == "hello"


def test_jsonl_multiple_snapshots(storage_dir):
    mgr = SessionManager(storage_dir=storage_dir)
    s = mgr.get_or_create("multi")
    s.add_message("user", "first")
    mgr.save(s)

    s.add_message("assistant", "second")
    mgr.save(s)

    # Reload — should get the latest snapshot
    mgr2 = SessionManager(storage_dir=storage_dir)
    loaded = mgr2.get("multi")
    assert len(loaded.messages) == 2


def test_session_manager_no_storage():
    mgr = SessionManager()
    s = mgr.get_or_create("mem_only")
    s.add_message("user", "hi")
    mgr.save(s)
    assert mgr.get("mem_only") is not None


def test_list_sessions_includes_disk(storage_dir):
    mgr = SessionManager(storage_dir=storage_dir)
    s = mgr.get_or_create("on_disk")
    mgr.save(s)

    keys = mgr.list_sessions()
    assert "on_disk" in keys
