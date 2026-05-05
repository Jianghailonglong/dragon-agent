from session.session import Session
from session.manager import SessionManager


def test_session_add_message():
    s = Session(key="test")
    s.add_message("user", "hello")
    assert len(s.messages) == 1
    assert s.messages[0] == {"role": "user", "content": "hello"}


def test_session_add_tool_result():
    s = Session(key="test")
    s.add_tool_result("tool_1", "result text")
    assert s.messages[0]["role"] == "user"
    assert s.messages[0]["content"][0]["type"] == "tool_result"
    assert s.messages[0]["content"][0]["tool_use_id"] == "tool_1"


def test_session_get_messages_returns_copy():
    s = Session(key="test")
    s.add_message("user", "hi")
    msgs = s.get_messages()
    msgs.append({"role": "assistant", "fake": True})
    assert len(s.messages) == 1  # original unchanged


def test_session_manager_get_or_create():
    mgr = SessionManager()
    s1 = mgr.get_or_create("key1")
    s2 = mgr.get_or_create("key1")
    assert s1 is s2


def test_session_manager_get_none():
    mgr = SessionManager()
    assert mgr.get("nonexistent") is None


def test_session_manager_save_and_list():
    mgr = SessionManager()
    s = mgr.get_or_create("a")
    mgr.save(s)
    assert "a" in mgr.list_sessions()
