import os
import pytest
from pathlib import Path

from config.loader import load_dotenv, load_config


def test_load_dotenv_basic(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=hello world\n")

    # clear if exists
    os.environ.pop("FOO", None)
    os.environ.pop("BAZ", None)

    load_dotenv(env_file)
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "hello world"

    # cleanup
    os.environ.pop("FOO", None)
    os.environ.pop("BAZ", None)


def test_load_dotenv_skips_comments(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nKEY=value\n# another\n")

    os.environ.pop("KEY", None)
    load_dotenv(env_file)
    assert os.environ["KEY"] == "value"
    os.environ.pop("KEY", None)


def test_load_dotenv_handles_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('QUOTED="hello world"\nSINGLE=\'foo bar\'\n')

    os.environ.pop("QUOTED", None)
    os.environ.pop("SINGLE", None)

    load_dotenv(env_file)
    assert os.environ["QUOTED"] == "hello world"
    assert os.environ["SINGLE"] == "foo bar"

    os.environ.pop("QUOTED", None)
    os.environ.pop("SINGLE", None)


def test_load_dotenv_no_override(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=from_file\n")

    os.environ["EXISTING"] = "from_env"
    load_dotenv(env_file)
    assert os.environ["EXISTING"] == "from_env"
    os.environ.pop("EXISTING", None)


def test_load_dotenv_missing_file(tmp_path):
    # should not raise
    load_dotenv(tmp_path / "nope.env")


def test_load_config_with_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-test-from-dotenv\n"
        "ANTHROPIC_BASE_URL=https://my-proxy.com\n"
        "ANTHROPIC_MODEL=mimo-v2.5\n"
    )

    # clear to avoid interference from real environment
    saved = {}
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"):
        saved[k] = os.environ.pop(k, None)
    try:
        cfg = load_config(dotenv_path=env_file, path=tmp_path / "nope.yaml")
        assert cfg.agents["default"].provider.api_key == "sk-test-from-dotenv"
        assert cfg.agents["default"].provider.base_url == "https://my-proxy.com"
        assert cfg.agents["default"].provider.model == "mimo-v2.5"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
