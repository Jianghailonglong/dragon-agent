import pytest
from tools.base import BaseTool
from tools.registry import ToolRegistry


class DummyTool(BaseTool):
    @property
    def name(self):
        return "dummy"

    @property
    def description(self):
        return "A dummy tool"

    @property
    def parameters(self):
        return {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, **kwargs):
        return f"echo: {kwargs.get('x', '')}"


@pytest.fixture
def registry():
    r = ToolRegistry()
    r.register(DummyTool())
    return r


def test_register_and_get(registry):
    assert "dummy" in registry
    assert registry.get("dummy").name == "dummy"
    assert registry.get("missing") is None


def test_list_schemas(registry):
    schemas = registry.list_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy"
    assert "input_schema" in schemas[0]


def test_len(registry):
    assert len(registry) == 1


@pytest.mark.asyncio
async def test_dummy_execute():
    tool = DummyTool()
    result = await tool.execute(x="world")
    assert result == "echo: world"
