"""Tests for the CSV adapter and record binding."""

from pathlib import Path

import pytest

from tests.conftest import SIMPLE_CSV, SIMPLE_MAP
from treeviewer.adapters.csv_adapter import CsvAdapter, adapter_for
from treeviewer.errors import MappingError
from treeviewer.mapping import bind_records, load_column_map
from treeviewer.model import TabularSource


def test_csv_adapter_reads_simple_example() -> None:
    table = CsvAdapter().read(SIMPLE_CSV)
    assert table.headers[0] == "Key"
    assert len(table.rows) == 5
    assert table.rows[0][0] == "root"


def test_csv_adapter_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        CsvAdapter().read(tmp_path / "missing.csv")


def test_csv_adapter_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(MappingError, match="empty"):
        CsvAdapter().read(path)


def test_adapter_for_rejects_unknown_suffix() -> None:
    with pytest.raises(MappingError, match="Unsupported"):
        adapter_for(Path("items.xlsx"))


def test_bind_records_maps_parents_and_data() -> None:
    table = CsvAdapter().read(SIMPLE_CSV)
    mapping = load_column_map(SIMPLE_MAP)
    records = bind_records(table, mapping)
    by_id = {record.id: record for record in records}
    assert by_id["root"].parent_ids == []
    assert by_id["a"].parent_ids == ["root"]
    assert by_id["shared"].parent_ids == ["a", "b"]
    assert by_id["a"].data[0].name == "Owner"
    assert by_id["a"].data[0].value == "Alex"
    assert by_id["a"].source_url == "https://jira.example.com/browse/WS-A"
    assert by_id["a"].subtitle == "a"


def test_bind_records_ignores_unselected_columns() -> None:
    table = TabularSource(
        headers=["id", "title", "secret"],
        rows=[("n1", "Node", "hidden")],
    )
    mapping = load_column_map(SIMPLE_MAP).model_copy(
        update={"id": "id", "title": "title", "status": None, "links": None, "data": [], "source_url": None}
    )
    records = bind_records(table, mapping)
    assert records[0].data == []


def test_semicolon_parent_lists() -> None:
    table = TabularSource(
        headers=["Key", "Summary", "Status", "Parent", "Owner", "Updated", "URL"],
        rows=[("x", "X", "Done", "a; b ;a", "Sam", "2026-01-01", "")],
    )
    mapping = load_column_map(SIMPLE_MAP)
    records = bind_records(table, mapping)
    assert records[0].parent_ids == ["a", "b"]
