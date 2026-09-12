"""Tests for graph validation and normalisation."""

import pytest

from tests.conftest import SIMPLE_CSV, SIMPLE_MAP
from treeviewer.convert import convert_csv
from treeviewer.errors import CycleError, GraphValidationError
from treeviewer.mapping import load_column_map
from treeviewer.model import ColumnMap, DataField, DocumentMeta, GraphDocument, Link, Node, RawRecord, Status
from treeviewer.normalize import normalize
from treeviewer.validate import validate


def _statuses() -> list[Status]:
    return [
        Status(id="ok", label="OK", color="#2e7d32", severity=0),
        Status(id="bad", label="Bad", color="#c62828", severity=1),
    ]


def _mapping() -> ColumnMap:
    return ColumnMap(
        id="id",
        title="title",
        status="status",
        links="parent",
        statuses=_statuses(),
        status_fallback="bad",
    )


def test_unknown_status_uses_fallback() -> None:
    records = [
        RawRecord(id="n", title="N", status="mystery", data=[]),
    ]
    document = normalize(records, _mapping(), title="t")
    assert document.nodes[0].status == "bad"


def test_unknown_status_strict() -> None:
    records = [RawRecord(id="n", title="N", status="mystery")]
    with pytest.raises(GraphValidationError, match="Unknown status"):
        normalize(records, _mapping(), title="t", strict=True)


def test_invalid_url_dropped() -> None:
    records = [RawRecord(id="n", title="N", status="ok", source_url="javascript:alert(1)")]
    document = normalize(records, _mapping(), title="t")
    assert document.nodes[0].source_url is None


def test_invalid_url_strict() -> None:
    records = [RawRecord(id="n", title="N", status="ok", source_url="not-a-url")]
    with pytest.raises(GraphValidationError, match="Invalid source URL"):
        normalize(records, _mapping(), title="t", strict=True)


def test_self_link_rejected() -> None:
    records = [RawRecord(id="n", title="N", status="ok", parent_ids=["n"])]
    with pytest.raises(GraphValidationError, match="Self-link"):
        normalize(records, _mapping(), title="t")


def test_duplicate_ids() -> None:
    records = [
        RawRecord(id="n", title="One", status="ok"),
        RawRecord(id="n", title="Two", status="ok"),
    ]
    document = normalize(records, _mapping(), title="t")
    with pytest.raises(GraphValidationError, match="Duplicate node"):
        validate(document)


def test_dangling_parent() -> None:
    records = [RawRecord(id="n", title="N", status="ok", parent_ids=["missing"])]
    document = normalize(records, _mapping(), title="t")
    with pytest.raises(GraphValidationError, match="missing parent"):
        validate(document)


def test_cycle_rejected() -> None:
    records = [
        RawRecord(id="a", title="A", status="ok", parent_ids=["b"]),
        RawRecord(id="b", title="B", status="ok", parent_ids=["a"]),
    ]
    document = normalize(records, _mapping(), title="t")
    with pytest.raises(CycleError, match="Cycle"):
        validate(document)


def test_empty_catalogue() -> None:
    document = GraphDocument(
        meta=DocumentMeta(title="t"),
        statuses=[],
        nodes=[],
        links=[],
    )
    with pytest.raises(GraphValidationError, match="at least one"):
        validate(document)


def test_simple_example_converts() -> None:
    mapping = load_column_map(SIMPLE_MAP)
    document = convert_csv(SIMPLE_CSV, mapping, title="Simple")
    ids = {node.id for node in document.nodes}
    assert ids == {"root", "a", "b", "b1", "shared"}
    assert any(link.from_id == "a" and link.to_id == "shared" for link in document.links)
    assert any(link.from_id == "b" and link.to_id == "shared" for link in document.links)
    shared = next(node for node in document.nodes if node.id == "shared")
    assert shared.data == [
        DataField(name="Owner", value="Sam"),
        DataField(name="Updated", value="2026-09-05"),
    ]
