"""Tests for column mapping and status catalogue prompts."""

from pathlib import Path

import pytest

from tests.conftest import SIMPLE_CSV, SIMPLE_MAP, ScriptedPrompt
from treeviewer.adapters.csv_adapter import CsvAdapter
from treeviewer.errors import MappingError
from treeviewer.mapping import (
    load_column_map,
    prompt_column_map,
    prompt_status_catalogue,
    save_column_map,
)
from treeviewer.model import Status


def test_load_column_map_resets_severity() -> None:
    mapping = load_column_map(SIMPLE_MAP)
    assert [status.id for status in mapping.statuses] == [
        "Done",
        "To Do",
        "In Progress",
        "Blocked",
    ]
    assert [status.severity for status in mapping.statuses] == [0, 1, 2, 3]
    assert mapping.status_fallback == "Blocked"
    assert mapping.data == ["Owner", "Updated"]


def test_prompt_status_catalogue_uses_defaults() -> None:
    io = ScriptedPrompt(
        [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    statuses, fallback = prompt_status_catalogue(
        ["Done", "To Do", "In Progress", "Blocked"],
        io,
    )
    assert [status.id for status in statuses] == ["Done", "To Do", "In Progress", "Blocked"]
    assert statuses[0].color == "#2e7d32"
    assert statuses[3].color == "#c62828"
    assert fallback == "Blocked"


def test_prompt_status_catalogue_custom_order_and_fallback() -> None:
    io = ScriptedPrompt(
        [
            "Blocked, Done",
            "At risk",
            "#111111",
            "Complete",
            "#222222",
            "Done",
        ]
    )
    statuses, fallback = prompt_status_catalogue(["Done", "Blocked"], io)
    assert statuses[0].id == "Blocked"
    assert statuses[0].label == "At risk"
    assert statuses[0].color == "#111111"
    assert statuses[1].label == "Complete"
    assert fallback == "Done"


def test_prompt_status_catalogue_rejects_bad_fallback() -> None:
    io = ScriptedPrompt(["Done", "", "", "missing"])
    with pytest.raises(MappingError, match="Fallback"):
        prompt_status_catalogue(["Done"], io)


def test_prompt_column_map_scripted() -> None:
    table = CsvAdapter().read(SIMPLE_CSV)
    io = ScriptedPrompt(
        [
            "1",
            "2",
            "3",
            "4",
            "5,6",
            "7",
            "Done, To Do, In Progress, Blocked",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Blocked",
        ]
    )
    mapping = prompt_column_map(table, io)
    assert mapping.id == "Key"
    assert mapping.title == "Summary"
    assert mapping.status == "Status"
    assert mapping.links == "Parent"
    assert mapping.data == ["Owner", "Updated"]
    assert mapping.source_url == "URL"
    assert mapping.status_fallback == "Blocked"


def test_prompt_column_map_reprompts_bad_index() -> None:
    table = CsvAdapter().read(SIMPLE_CSV)
    io = ScriptedPrompt(
        [
            "99",
            "x",
            "1",
            "",
            "",
            "",
            "",
            "",
            "none",
            "",
        ]
    )
    mapping = prompt_column_map(table, io)
    assert mapping.id == "Key"
    assert mapping.title == "Key"
    assert mapping.status is None
    assert mapping.statuses[0].id == "none"


def test_save_and_reload_map(tmp_path: Path) -> None:
    original = load_column_map(SIMPLE_MAP)
    dest = tmp_path / "saved.map.json"
    save_column_map(original, dest)
    reloaded = load_column_map(dest)
    assert reloaded.id == original.id
    assert reloaded.statuses == original.statuses


def test_load_column_map_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_column_map(tmp_path / "nope.json")


def test_status_model_accepts_explicit_colour() -> None:
    status = Status(id="x", label="X", color="#abcdef", severity=0)
    assert status.color == "#abcdef"
