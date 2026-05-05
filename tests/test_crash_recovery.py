import pytest
from session.session import Session


def test_pending_user_turn():
    s = Session(key="test")
    assert not s.has_pending_user_turn()

    s.mark_pending_user_turn()
    assert s.has_pending_user_turn()

    s.clear_pending_user_turn()
    assert not s.has_pending_user_turn()


def test_runtime_checkpoint():
    s = Session(key="test")
    assert s.get_runtime_checkpoint() is None

    s.set_runtime_checkpoint({"last_tool_index": 2, "tool_name": "exec"})
    cp = s.get_runtime_checkpoint()
    assert cp["last_tool_index"] == 2
    assert cp["tool_name"] == "exec"

    s.clear_runtime_checkpoint()
    assert s.get_runtime_checkpoint() is None


def test_session_serialization_preserves_metadata():
    s = Session(key="test")
    s.add_message("user", "hi")
    s.mark_pending_user_turn()
    s.set_runtime_checkpoint({"step": 1})

    d = s.to_dict()
    restored = Session.from_dict(d)

    assert restored.key == "test"
    assert len(restored.messages) == 1
    assert restored.has_pending_user_turn()
    assert restored.get_runtime_checkpoint()["step"] == 1
