import pytest
import tempfile
import os
from pathlib import Path

from tools.builtin.read_file import ReadFileTool
from tools.builtin.exec import ExecTool


@pytest.fixture
def tmp_workspace(tmp_path):
    return str(tmp_path)


@pytest.mark.asyncio
async def test_read_file(tmp_workspace):
    p = Path(tmp_workspace) / "test.txt"
    p.write_text("hello\nworld\nline3\n")

    tool = ReadFileTool(workspace=tmp_workspace)
    result = await tool.execute(path="test.txt")
    assert "hello" in result
    assert "world" in result


@pytest.mark.asyncio
async def test_read_file_offset_limit(tmp_workspace):
    p = Path(tmp_workspace) / "test.txt"
    p.write_text("a\nb\nc\nd\ne\n")

    tool = ReadFileTool(workspace=tmp_workspace)
    result = await tool.execute(path="test.txt", offset=1, limit=2)
    lines = result.strip().splitlines()
    assert lines == ["b", "c"]


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_workspace):
    tool = ReadFileTool(workspace=tmp_workspace)
    result = await tool.execute(path="nope.txt")
    assert "Error" in result or "not found" in result


@pytest.mark.asyncio
async def test_read_file_boundary(tmp_workspace):
    tool = ReadFileTool(workspace=tmp_workspace)
    result = await tool.execute(path="../outside.txt")
    assert "Error" in result or "outside" in result


@pytest.mark.asyncio
async def test_exec(tmp_workspace):
    tool = ExecTool(workspace=tmp_workspace, timeout=5)
    result = await tool.execute(command="echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_exec_nonzero(tmp_workspace):
    tool = ExecTool(workspace=tmp_workspace, timeout=5)
    result = await tool.execute(command="exit 1")
    assert "exit code" in result
