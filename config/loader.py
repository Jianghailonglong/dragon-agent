from __future__ import annotations

import os
from pathlib import Path

import yaml

from .schema import DragonConfig


def find_project_root() -> Path:
    """Walk up from this file to find the project root (where pyproject.toml lives)."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def load_dotenv(path: str | Path | None = None) -> None:
    """Load environment variables from a .env file into os.environ."""
    if path is None:
        # Search project root first, then cwd
        project_root = find_project_root()
        candidates = [project_root / ".env", Path.cwd() / ".env"]
        p = None
        for c in candidates:
            if c.exists():
                p = c
                break
        if p is None:
            return
    else:
        p = Path(path)
        if not p.exists():
            return

    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # remove optional quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            # don't override existing env vars
            if key not in os.environ:
                os.environ[key] = value


def load_config(
    path: str | Path | None = None,
    dotenv_path: str | Path | None = None,
) -> DragonConfig:
    """Load configuration: .env → env vars → YAML → DragonConfig."""
    # 1. Load .env file
    if dotenv_path is not None:
        load_dotenv(dotenv_path)
    else:
        # Auto-find .env from project root
        load_dotenv()

    # 2. Load YAML config
    if path is None:
        path = os.environ.get("DRAGON_CONFIG", "dragon.yaml")

    p = Path(path)
    if not p.is_absolute():
        p = find_project_root() / p
    if p.exists():
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # 3. Env overrides for agent provider configs
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    model = os.environ.get("ANTHROPIC_MODEL", "")
    if api_key or base_url or model:
        data.setdefault("agents", {})
        if isinstance(data["agents"], dict):
            data["agents"].setdefault("default", {})
            for agent_cfg in data["agents"].values():
                if isinstance(agent_cfg, dict):
                    agent_cfg.setdefault("provider", {})
                    if isinstance(agent_cfg["provider"], dict):
                        if api_key:
                            agent_cfg["provider"].setdefault("api_key", api_key)
                        if base_url:
                            agent_cfg["provider"].setdefault("base_url", base_url)
                        if model:
                            agent_cfg["provider"].setdefault("model", model)

    return DragonConfig.model_validate(data)
