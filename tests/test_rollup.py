"""Tests for worst-wins status roll-up."""

from tests.conftest import FOUR_LEVEL_CSV, FOUR_LEVEL_MAP, SIMPLE_CSV, SIMPLE_MAP
from treeviewer.convert import convert_csv
from treeviewer.mapping import load_column_map
from treeviewer.model import DocumentMeta, GraphDocument, Link, Node, Status
from treeviewer.rollup import WorstWinsRollup
from treeviewer.validate import validate


def _status(item_id: str, severity: int) -> Status:
    return Status(id=item_id, label=item_id, color="#000000", severity=severity)


def _node(item_id: str, status: str, child_ids: list[str] | None = None) -> Node:
    return Node(
        id=item_id,
        title=item_id,
        status=status,
        rollup_status=status,
        child_ids=child_ids or [],
    )


def test_leaf_rollup_equals_own_status() -> None:
    document = GraphDocument(
        meta=DocumentMeta(title="t"),
        statuses=[_status("ok", 0)],
        nodes=[_node("leaf", "ok")],
        links=[],
    )
    rolled = WorstWinsRollup().compute(validate(document))
    assert rolled.nodes[0].rollup_status == "ok"


def test_worst_descendant_wins() -> None:
    document = GraphDocument(
        meta=DocumentMeta(title="t"),
        statuses=[_status("ok", 0), _status("bad", 1)],
        nodes=[
            _node("root", "ok", ["child"]),
            _node("child", "ok", ["leaf"]),
            _node("leaf", "bad"),
        ],
        links=[
            Link(from_id="root", to_id="child"),
            Link(from_id="child", to_id="leaf"),
        ],
    )
    rolled = WorstWinsRollup().compute(validate(document))
    by_id = {node.id: node for node in rolled.nodes}
    assert by_id["leaf"].rollup_status == "bad"
    assert by_id["child"].rollup_status == "bad"
    assert by_id["root"].rollup_status == "bad"


def test_dag_two_parents_share_child_rollup() -> None:
    mapping = load_column_map(SIMPLE_MAP)
    document = convert_csv(SIMPLE_CSV, mapping, title="Simple")
    by_id = {node.id: node for node in document.nodes}
    assert by_id["b1"].rollup_status == "Blocked"
    assert by_id["b"].rollup_status == "Blocked"
    assert by_id["a"].rollup_status == "To Do"
    assert by_id["shared"].rollup_status == "To Do"
    assert by_id["root"].rollup_status == "Blocked"


def test_isolated_node() -> None:
    document = GraphDocument(
        meta=DocumentMeta(title="t"),
        statuses=[_status("ok", 0), _status("bad", 1)],
        nodes=[_node("alone", "ok")],
        links=[],
    )
    rolled = WorstWinsRollup().compute(validate(document))
    assert rolled.nodes[0].rollup_status == "ok"


def test_four_level_example_has_four_roots() -> None:
    mapping = load_column_map(FOUR_LEVEL_MAP)
    document = convert_csv(FOUR_LEVEL_CSV, mapping, title="Four level")
    child_ids = {link.to_id for link in document.links}
    roots = [node.id for node in document.nodes if node.id not in child_ids]
    assert roots == ["PLAT", "MOB", "DATA", "SEC"]
    by_id = {node.id: node for node in document.nodes}
    assert by_id["DATA"].rollup_status == "Blocked"
    assert by_id["PLAT-E-A11Y"].rollup_status == "Done"
