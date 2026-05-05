import pytest
import json
from pathlib import Path

from core.logger import ConversationLogger


@pytest.fixture
def logger(tmp_path):
    return ConversationLogger(log_dir=str(tmp_path / "logs"))


def test_log_user_message(logger, tmp_path):
    logger.log_user_message("cli:test", "hello")
    log_file = tmp_path / "logs" / "cli_test.jsonl"
    assert log_file.exists()
    entry = json.loads(log_file.read_text().strip())
    assert entry["role"] == "user"
    assert entry["content"] == "hello"


def test_log_assistant_message(logger, tmp_path):
    logger.log_assistant_message("cli:test", "hi there", iterations=3, usage={"input_tokens": 100})
    log_file = tmp_path / "logs" / "cli_test.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["role"] == "assistant"
    assert entry["iterations"] == 3
    assert entry["usage"]["input_tokens"] == 100


def test_log_tool_call(logger, tmp_path):
    logger.log_tool_call("cli:test", "read_file", {"path": "test.txt"}, "file contents here")
    log_file = tmp_path / "logs" / "cli_test.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["role"] == "tool"
    assert entry["tool_name"] == "read_file"


def test_log_error(logger, tmp_path):
    logger.log_error("cli:test", "something broke")
    log_file = tmp_path / "logs" / "cli_test.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["role"] == "error"


def test_multiple_entries_appended(logger, tmp_path):
    logger.log_user_message("cli:test", "msg1")
    logger.log_assistant_message("cli:test", "reply1")
    logger.log_user_message("cli:test", "msg2")

    log_file = tmp_path / "logs" / "cli_test.jsonl"
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 3
