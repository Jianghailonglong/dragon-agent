import pytest

from tools.safety import ToolSafetyGuard


@pytest.fixture
def guard(tmp_path):
    return ToolSafetyGuard(workspace=str(tmp_path), max_repeated_lookups=2)


# --- Workspace boundary ---

def test_workspace_boundary_safe(guard, tmp_path):
    (tmp_path / "file.txt").write_text("ok")
    assert guard.check_workspace_boundary("read_file", str(tmp_path / "file.txt")) is None


def test_workspace_boundary_outside(guard):
    result = guard.check_workspace_boundary("read_file", "/etc/passwd")
    assert result is not None
    assert "outside" in result


def test_workspace_boundary_irrelevant_tool(guard):
    assert guard.check_workspace_boundary("exec", "/etc/passwd") is None


# --- URL safety ---

def test_url_safety_normal(guard):
    assert guard.check_url_safety("https://example.com/page") is None


def test_url_safety_localhost(guard):
    assert guard.check_url_safety("http://localhost:8080/admin") is not None


def test_url_safety_private_ip(guard):
    assert guard.check_url_safety("http://192.168.1.1/admin") is not None
    assert guard.check_url_safety("http://10.0.0.1/metadata") is not None


def test_url_safety_metadata_endpoint(guard):
    assert guard.check_url_safety("http://169.254.169.254/latest/meta-data/") is not None


def test_url_safety_internal_domain(guard):
    assert guard.check_url_safety("http://db.internal/query") is not None


def test_url_safety_public(guard):
    assert guard.check_url_safety("https://api.github.com/repos") is None


# --- Repeated lookup ---

def test_repeated_lookup_within_limit(guard):
    for _ in range(2):
        assert guard.check_repeated_lookup("web_search", {"query": "test"}) is None


def test_repeated_lookup_exceeds_limit(guard):
    for _ in range(2):
        guard.check_repeated_lookup("web_search", {"query": "test"})
    result = guard.check_repeated_lookup("web_search", {"query": "test"})
    assert result is not None
    assert "infinite loop" in result


def test_repeated_lookup_different_queries(guard):
    for _ in range(3):
        guard.check_repeated_lookup("web_search", {"query": "different"})
    # Different queries don't share counter
    assert guard.check_repeated_lookup("web_search", {"query": "other"}) is None


def test_repeated_lookup_reset(guard):
    for _ in range(5):
        guard.check_repeated_lookup("web_search", {"query": "test"})
    guard.reset_counts()
    assert guard.check_repeated_lookup("web_search", {"query": "test"}) is None


# --- check_all ---

def test_check_all_catches_workspace(guard):
    result = guard.check_all("read_file", {"path": "/etc/passwd"})
    assert result is not None


def test_check_all_catches_url(guard):
    result = guard.check_all("web_fetch", {"url": "http://localhost:8080"})
    assert result is not None


def test_check_all_passes(guard):
    assert guard.check_all("exec", {"command": "echo hello"}) is None
