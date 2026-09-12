"""Orchestrate CSV import into a graph document."""

from pathlib import Path

from treeviewer.adapters.csv_adapter import adapter_for
from treeviewer.errors import MappingError
from treeviewer.io import PromptIO
from treeviewer.mapping import bind_records, load_column_map, prompt_column_map, save_column_map
from treeviewer.model import ColorMode, ColumnMap, GraphDocument, TabularSource
from treeviewer.normalize import normalize
from treeviewer.rollup import strategy_for
from treeviewer.validate import validate
from treeviewer.write import write_graph


def convert_csv(
    csv_path: Path,
    mapping: ColumnMap,
    *,
    title: str,
    description: str = "",
    color_mode: ColorMode = "own",
    delimiter: str = ",",
    adapter: str | None = None,
    strict: bool = False,
    rollup: str = "worst_wins",
) -> GraphDocument:
    """Convert a CSV file to a validated graph document.

    Args:
        csv_path: Source CSV.
        mapping: Column roles and status catalogue.
        title: Document title.
        description: Optional header subtitle.
        color_mode: Initial viewer colour mode.
        delimiter: CSV field separator.
        adapter: Optional adapter name. Defaults from the file suffix.
        strict: Reject unknown statuses and invalid URLs.
        rollup: Roll-up strategy name.

    Returns:
        A document ready to write as `graph.json`.

    Raises:
        FileNotFoundError: If the CSV is missing.
        MappingError: If mapping or the file format is invalid.
        treeviewer.errors.GraphValidationError: If the graph is invalid.
    """
    table = adapter_for(csv_path, adapter).read(csv_path, delimiter=delimiter)
    return convert_table(
        table,
        mapping,
        title=title,
        description=description,
        color_mode=color_mode,
        strict=strict,
        rollup=rollup,
    )


def convert_table(
    table: TabularSource,
    mapping: ColumnMap,
    *,
    title: str,
    description: str = "",
    color_mode: ColorMode = "own",
    strict: bool = False,
    rollup: str = "worst_wins",
) -> GraphDocument:
    """Convert an in-memory table to a graph document.

    Args:
        table: Headered rows.
        mapping: Column roles and status catalogue.
        title: Document title.
        description: Optional header subtitle.
        color_mode: Initial viewer colour mode.
        strict: Reject unknown statuses and invalid URLs.
        rollup: Roll-up strategy name.

    Returns:
        A document ready to write as `graph.json`.
    """
    records = bind_records(table, mapping)
    document = normalize(
        records,
        mapping,
        title=title,
        description=description,
        color_mode=color_mode,
        strict=strict,
    )
    validated = validate(document)
    return strategy_for(rollup).compute(validated)


def resolve_mapping(
    table: TabularSource,
    *,
    map_path: Path | None,
    io: PromptIO | None,
    save_map_path: Path | None = None,
) -> ColumnMap:
    """Load a saved map or prompt for one.

    Args:
        table: Loaded CSV, used when prompting.
        map_path: Optional saved map.
        io: Prompt port. Required when `map_path` is omitted.
        save_map_path: If set, write the chosen map after resolution.

    Returns:
        The column map to use for conversion.

    Raises:
        MappingError: If neither a map file nor a prompt port is available.
    """
    if map_path is not None:
        mapping = load_column_map(map_path)
    elif io is not None:
        mapping = prompt_column_map(table, io)
    else:
        raise MappingError("A --map file is required when stdin is not a TTY")

    if save_map_path is not None:
        save_column_map(mapping, save_map_path)
    return mapping


def convert_and_write(
    csv_path: Path,
    out_path: Path,
    mapping: ColumnMap,
    *,
    title: str,
    description: str = "",
    color_mode: ColorMode = "own",
    delimiter: str = ",",
    adapter: str | None = None,
    strict: bool = False,
    rollup: str = "worst_wins",
) -> GraphDocument:
    """Convert a CSV file and write `graph.json`.

    Args:
        csv_path: Source CSV.
        out_path: Destination JSON.
        mapping: Column roles and status catalogue.
        title: Document title.
        description: Optional header subtitle.
        color_mode: Initial viewer colour mode.
        delimiter: CSV field separator.
        adapter: Optional adapter name.
        strict: Reject unknown statuses and invalid URLs.
        rollup: Roll-up strategy name.

    Returns:
        The document that was written.
    """
    document = convert_csv(
        csv_path,
        mapping,
        title=title,
        description=description,
        color_mode=color_mode,
        delimiter=delimiter,
        adapter=adapter,
        strict=strict,
        rollup=rollup,
    )
    write_graph(document, out_path)
    return document
