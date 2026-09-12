"""CLI convert tests."""

from pathlib import Path

from tests.conftest import SIMPLE_CSV, SIMPLE_MAP
from treeviewer.cli import main
from treeviewer.model import GraphDocument


def test_cli_convert_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "graph.json"
    code = main(
        [
            "convert",
            str(SIMPLE_CSV),
            "--map",
            str(SIMPLE_MAP),
            "--title",
            "Simple tree",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    document = GraphDocument.model_validate_json(out.read_text(encoding="utf-8"))
    assert document.meta.title == "Simple tree"
    assert len(document.nodes) == 5
    root = next(node for node in document.nodes if node.id == "root")
    assert root.rollup_status == "Blocked"
    assert root.child_ids == ["a", "b"]


def test_cli_missing_map_without_tty(tmp_path: Path) -> None:
    out = tmp_path / "graph.json"
    code = main(["convert", str(SIMPLE_CSV), "--out", str(out)])
    assert code == 1
    assert not out.exists()
