import pytest
from pathlib import Path

from tools.builtin.write_file import WriteFileTool
from tools.builtin.edit_file import EditFileTool
from tools.builtin.grep_tool import GrepTool
from tools.builtin.glob_tool import GlobTool


@pytest.fixture
def ws(tmp_path):
    return str(tmp_path)


# --- write_file ---

@pytest.mark.asyncio
async def test_write_file(ws):
    tool = WriteFileTool(workspace=ws)
    result = await tool.execute(path="test.txt", content="hello world")
    assert "Wrote" in result
    assert (Path(ws) / "test.txt").read_text() == "hello world"


@pytest.mark.asyncio
async def test_write_file_creates_dirs(ws):
    tool = WriteFileTool(workspace=ws)
    result = await tool.execute(path="a/b/c.txt", content="nested")
    assert (Path(ws) / "a" / "b" / "c.txt").read_text() == "nested"


@pytest.mark.asyncio
async def test_write_file_boundary(ws):
    tool = WriteFileTool(workspace=ws)
    result = await tool.execute(path="../outside.txt", content="bad")
    assert "Error" in result or "outside" in result


# --- edit_file ---

@pytest.mark.asyncio
async def test_edit_file(ws):
    p = Path(ws) / "edit.txt"
    p.write_text("hello world")
    tool = EditFileTool(workspace=ws)
    result = await tool.execute(path="edit.txt", old_string="world", new_string="python")
    assert "Replaced" in result
    assert p.read_text() == "hello python"


@pytest.mark.asyncio
async def test_edit_file_not_found(ws):
    tool = EditFileTool(workspace=ws)
    result = await tool.execute(path="nope.txt", old_string="a", new_string="b")
    assert "Error" in result or "not found" in result


@pytest.mark.asyncio
async def test_edit_file_string_not_found(ws):
    p = Path(ws) / "edit.txt"
    p.write_text("hello world")
    tool = EditFileTool(workspace=ws)
    result = await tool.execute(path="edit.txt", old_string="xyz", new_string="abc")
    assert "not found" in result


# --- grep ---

@pytest.mark.asyncio
async def test_grep(ws):
    (Path(ws) / "a.py").write_text("def foo():\n    pass\n")
    (Path(ws) / "b.py").write_text("def bar():\n    pass\n")
    tool = GrepTool(workspace=ws)
    result = await tool.execute(pattern="def ", glob="*.py")
    assert "foo" in result
    assert "bar" in result


@pytest.mark.asyncio
async def test_grep_no_matches(ws):
    (Path(ws) / "a.py").write_text("nothing here")
    tool = GrepTool(workspace=ws)
    result = await tool.execute(pattern="xyz123")
    assert "no matches" in result


@pytest.mark.asyncio
async def test_grep_invalid_regex(ws):
    tool = GrepTool(workspace=ws)
    result = await tool.execute(pattern="[invalid")
    assert "Error" in result


# --- glob ---

@pytest.mark.asyncio
async def test_glob(ws):
    (Path(ws) / "a.py").write_text("")
    (Path(ws) / "b.txt").write_text("")
    (Path(ws) / "sub").mkdir()
    (Path(ws) / "sub" / "c.py").write_text("")

    tool = GlobTool(workspace=ws)
    result = await tool.execute(pattern="**/*.py")
    assert "a.py" in result
    assert "c.py" in result
    assert "b.txt" not in result


@pytest.mark.asyncio
async def test_glob_no_files(ws):
    tool = GlobTool(workspace=ws)
    result = await tool.execute(pattern="*.xyz")
    assert "no files" in result
