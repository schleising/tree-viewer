"""CSV source adapter."""

import csv
from pathlib import Path

from treeviewer.errors import MappingError
from treeviewer.model import TabularSource


class CsvAdapter:
    """Reads a UTF-8 CSV file with a header row."""

    def read(self, path: Path, *, delimiter: str = ",") -> TabularSource:
        """Load headers and rows from `path`.

        Args:
            path: CSV file.
            delimiter: Field separator.

        Returns:
            A table whose rows are padded or trimmed to the header length.

        Raises:
            FileNotFoundError: If `path` is missing.
            MappingError: If the file is empty or has a blank header.
        """
        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            try:
                headers = next(reader)
            except StopIteration as exc:
                raise MappingError(f"CSV file is empty: {path}") from exc
            if not headers or all(name.strip() == "" for name in headers):
                raise MappingError(f"CSV file has no header row: {path}")
            cleaned_headers = [name.strip() for name in headers]
            rows = [_normalise_row(row, len(cleaned_headers)) for row in reader]

        return TabularSource(headers=cleaned_headers, rows=rows)


def _normalise_row(row: list[str], width: int) -> tuple[str, ...]:
    """Pad or trim a CSV row so it matches the header count."""
    cells = list(row)
    if len(cells) < width:
        cells.extend([""] * (width - len(cells)))
    return tuple(cells[:width])


def adapter_for(path: Path, name: str | None = None) -> CsvAdapter:
    """Return a source adapter for `path`.

    Args:
        path: Input file.
        name: Optional adapter name. Only `csv` is supported in v1.

    Returns:
        A CSV adapter.

    Raises:
        MappingError: If the adapter name or suffix is unsupported.
    """
    kind = (name or path.suffix.lstrip(".")).lower()
    if kind in {"", "csv"}:
        return CsvAdapter()
    raise MappingError(f"Unsupported adapter: {kind}")
