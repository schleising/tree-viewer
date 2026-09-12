"""CSV-to-JSON converter for the tree viewer.

The package reads a single hierarchical CSV, maps columns interactively or
from a saved map, and writes the shared `graph.json` document consumed by
the static web viewer.
"""

from treeviewer.convert import convert_csv, convert_table
from treeviewer.model import ColumnMap, GraphDocument, Node, Status

__all__ = [
    "ColumnMap",
    "GraphDocument",
    "Node",
    "Status",
    "convert_csv",
    "convert_table",
]
