from config.schema import DragonConfig, AgentConfig, ProviderConfig


def test_default_config():
    cfg = DragonConfig()
    assert cfg.default_agent == "default"
    assert "default" in cfg.agents
    assert cfg.concurrency_limit == 4


def test_agent_config_defaults():
    ac = AgentConfig()
    assert ac.provider.type == "anthropic"
    assert ac.max_iterations == 20


def test_provider_config():
    pc = ProviderConfig(api_key="sk-test", model="claude-sonnet-4-20250514")
    assert pc.type == "anthropic"
    assert pc.max_tokens == 4096
