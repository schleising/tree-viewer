"""Adapter protocol for tabular sources."""

from pathlib import Path
from typing import Protocol

from treeviewer.model import TabularSource


class SourceAdapter(Protocol):
    """Reads a file into a headered table of string cells."""

    def read(self, path: Path, *, delimiter: str = ",") -> TabularSource:
        """Load a tabular source.

        Args:
            path: File to read.
            delimiter: Field separator. Adapters that do not use delimiters
                may ignore this argument.

        Returns:
            Headers plus data rows.

        Raises:
            FileNotFoundError: If `path` does not exist.
            treeviewer.errors.MappingError: If the file has no header row.
        """
        ...
