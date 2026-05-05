import pytest
from pathlib import Path

from intelligence.memory import MemoryStore


def test_memory_load_empty(tmp_path):
    store = MemoryStore(workspace=str(tmp_path))
    assert store.load() == ""


def test_memory_save_and_load(tmp_path):
    store = MemoryStore(workspace=str(tmp_path))
    store.save_entry("user_role", "Senior Python dev", "user")

    content = store.load()
    assert "user_role" in content
    assert "Senior Python dev" in content


def test_memory_list_entries(tmp_path):
    store = MemoryStore(workspace=str(tmp_path))
    store.save_entry("pref1", "likes dark mode", "feedback")
    store.save_entry("note1", "project deadline friday", "project")

    entries = store.list_entries()
    assert len(entries) == 2
    assert entries[0]["name"] == "pref1"
    assert entries[1]["type"] == "project"


def test_memory_clear(tmp_path):
    store = MemoryStore(workspace=str(tmp_path))
    store.save_entry("test", "data", "note")
    assert store.load() != ""

    store.clear()
    assert store.load() == ""
    assert store.list_entries() == []
