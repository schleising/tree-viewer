"""Serialize a graph document to JSON."""

from pathlib import Path

from treeviewer.model import GraphDocument


def write_graph(document: GraphDocument, path: Path) -> None:
    """Write `document` as pretty-printed JSON.

    Args:
        document: Validated graph with roll-up statuses.
        path: Destination file. Parent directories are created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        document.model_dump_json(indent=2, by_alias=True, exclude_none=True) + "\n",
        encoding="utf-8",
    )
