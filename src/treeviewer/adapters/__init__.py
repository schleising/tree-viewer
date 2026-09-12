"""Source adapters that load tabular data."""

from treeviewer.adapters.base import SourceAdapter
from treeviewer.adapters.csv_adapter import CsvAdapter, adapter_for

__all__ = ["CsvAdapter", "SourceAdapter", "adapter_for"]
