"""Interactive and file-based column mapping and status catalogues."""

from pathlib import Path

from treeviewer.errors import MappingError
from treeviewer.io import PromptIO
from treeviewer.model import (
    ColumnMap,
    DataField,
    RawRecord,
    Status,
    TabularSource,
    neutral_status,
    with_ordered_severity,
)

SUGGESTED_COLORS = (
    "#2e7d32",
    "#1565c0",
    "#f9a825",
    "#c62828",
    "#6a1b9a",
    "#00838f",
    "#ef6c00",
    "#546e7a",
)


def load_column_map(path: Path) -> ColumnMap:
    """Load a saved column map from JSON.

    Args:
        path: Map file written by `--save-map`.

    Returns:
        The validated map, with severity reset from list order.

    Raises:
        FileNotFoundError: If `path` is missing.
        MappingError: If the file is not a valid map.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Map file not found: {path}")
    try:
        mapping = ColumnMap.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise MappingError(f"Invalid map file {path}: {exc}") from exc
    return _finalise_map(mapping)


def save_column_map(mapping: ColumnMap, path: Path) -> None:
    """Write `mapping` as pretty-printed JSON.

    Args:
        mapping: Map to persist.
        path: Destination file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        mapping.model_dump_json(indent=2, by_alias=True, exclude_none=True) + "\n",
        encoding="utf-8",
    )


def header_index(table: TabularSource) -> dict[str, int]:
    """Return a header-to-index lookup.

    Args:
        table: Loaded CSV table.

    Returns:
        Map of header name to column index.

    Raises:
        MappingError: If a header is duplicated.
    """
    lookup: dict[str, int] = {}
    for index, header in enumerate(table.headers):
        if header in lookup:
            raise MappingError(f"Duplicate CSV header: {header}")
        lookup[header] = index
    return lookup


def bind_records(table: TabularSource, mapping: ColumnMap) -> list[RawRecord]:
    """Bind table rows to `RawRecord` using `mapping`.

    Args:
        table: Loaded CSV table.
        mapping: Column roles chosen at import.

    Returns:
        One record per non-empty id row.

    Raises:
        MappingError: If a mapped header is missing or an id is empty.
    """
    lookup = header_index(table)
    id_index = _require_header(lookup, mapping.id, "item id")
    title_index = _require_header(lookup, mapping.title, "item title")
    status_index = _optional_header(lookup, mapping.status, "status")
    links_index = _optional_header(lookup, mapping.links, "links")
    url_index = _optional_header(lookup, mapping.source_url, "source URL")
    data_indexes = [
        (_require_header(lookup, name, "data"), name) for name in mapping.data
    ]

    records: list[RawRecord] = []
    for row_number, row in enumerate(table.rows, start=2):
        item_id = row[id_index].strip()
        if item_id == "":
            if _row_is_blank(row):
                continue
            raise MappingError(f"Row {row_number} has an empty item id")
        title = row[title_index].strip() or item_id
        status = row[status_index].strip() if status_index is not None else None
        parent_ids = _parse_parent_ids(row[links_index]) if links_index is not None else []
        source_url = row[url_index].strip() if url_index is not None else None
        data = [
            DataField(name=name, value=row[index].strip())
            for index, name in data_indexes
        ]
        subtitle = item_id if title != item_id else None
        records.append(
            RawRecord(
                id=item_id,
                title=title,
                subtitle=subtitle,
                status=None if status == "" else status,
                parent_ids=parent_ids,
                source_url=None if source_url == "" else source_url,
                data=data,
            )
        )
    return records


def distinct_status_values(table: TabularSource, status_column: str) -> list[str]:
    """Return first-seen non-empty values from the status column.

    Args:
        table: Loaded CSV table.
        status_column: Header of the status column.

    Returns:
        Distinct status strings in file order.

    Raises:
        MappingError: If the column is missing.
    """
    lookup = header_index(table)
    index = _require_header(lookup, status_column, "status")
    seen: set[str] = set()
    values: list[str] = []
    for row in table.rows:
        value = row[index].strip()
        if value == "" or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def prompt_column_map(table: TabularSource, io: PromptIO) -> ColumnMap:
    """Ask the user to choose columns and define the status catalogue.

    Args:
        table: Loaded CSV table.
        io: Prompt port.

    Returns:
        A complete column map.

    Raises:
        MappingError: If prompting fails after invalid input, or the table
            has no columns.
    """
    if not table.headers:
        raise MappingError("CSV file has no columns")

    io.tell("Columns in input:")
    for index, header in enumerate(table.headers, start=1):
        io.tell(f"  {index}) {header}")

    id_index = _ask_index(io, "Item id column", table.headers, optional=False)
    if id_index is None:
        raise MappingError("An item id column is required")
    title_index = _ask_index(
        io,
        "Item title column (blank = same as id)",
        table.headers,
        optional=True,
    )
    status_index = _ask_index(io, "Status column (blank = none)", table.headers, optional=True)
    links_index = _ask_index(
        io,
        "Links / parent column (blank = none)",
        table.headers,
        optional=True,
    )
    data_indexes = _ask_index_list(
        io,
        "Data columns to show on each node (comma-separated, blank = none)",
        table.headers,
    )
    url_index = _ask_index(io, "Source URL column (blank = none)", table.headers, optional=True)

    status_header = table.headers[status_index] if status_index is not None else None
    statuses, fallback = _prompt_or_neutral_catalogue(table, status_header, io)

    return ColumnMap(
        id=table.headers[id_index],
        title=table.headers[title_index] if title_index is not None else table.headers[id_index],
        status=status_header,
        links=table.headers[links_index] if links_index is not None else None,
        data=[table.headers[index] for index in data_indexes],
        source_url=table.headers[url_index] if url_index is not None else None,
        statuses=statuses,
        status_fallback=fallback,
    )


def prompt_status_catalogue(
    found: list[str],
    io: PromptIO,
) -> tuple[list[Status], str]:
    """Ask the user to order, label, and colour statuses.

    Args:
        found: Distinct values from the status column.
        io: Prompt port.

    Returns:
        Catalogue in severity order and the fallback status id.

    Raises:
        MappingError: If the resulting catalogue is empty or the fallback
            is not in the list.
    """
    default_order = ", ".join(found)
    io.tell(f"Distinct values in Status: {default_order or '(none)'}")
    ordered = _ask_status_order(io, found)
    statuses: list[Status] = []
    for index, status_id in enumerate(ordered):
        suggested = SUGGESTED_COLORS[index % len(SUGGESTED_COLORS)]
        label = _ask_line(io, f"Label for '{status_id}' [{status_id}]: ", status_id)
        color = _ask_line(io, f"Colour for '{status_id}' [{suggested}]: ", suggested)
        statuses.append(Status(id=status_id, label=label, color=color, severity=index))

    if not statuses:
        raise MappingError("Status catalogue must have at least one entry")

    default_fallback = statuses[-1].id
    fallback = _ask_line(
        io,
        f"Fallback status for blank or unrecognised values [{default_fallback}]: ",
        default_fallback,
    )
    ids = {item.id for item in statuses}
    if fallback not in ids:
        raise MappingError(f"Fallback status {fallback!r} is not in the catalogue")
    return statuses, fallback


def _prompt_or_neutral_catalogue(
    table: TabularSource,
    status_header: str | None,
    io: PromptIO,
) -> tuple[list[Status], str]:
    if status_header is None:
        status = neutral_status()
        return [status], status.id
    found = distinct_status_values(table, status_header)
    return prompt_status_catalogue(found, io)


def _finalise_map(mapping: ColumnMap) -> ColumnMap:
    statuses = list(mapping.statuses)
    fallback = mapping.status_fallback
    if not statuses:
        status = neutral_status()
        statuses = [status]
        fallback = status.id
    statuses = with_ordered_severity(statuses)
    if fallback is None:
        fallback = statuses[-1].id
    ids = {item.id for item in statuses}
    if fallback not in ids:
        raise MappingError(f"Fallback status {fallback!r} is not in the catalogue")
    return mapping.model_copy(update={"statuses": statuses, "status_fallback": fallback})


def _require_header(lookup: dict[str, int], header: str, role: str) -> int:
    if header not in lookup:
        raise MappingError(f"CSV has no {role} column named {header!r}")
    return lookup[header]


def _optional_header(lookup: dict[str, int], header: str | None, role: str) -> int | None:
    if header is None:
        return None
    return _require_header(lookup, header, role)


def _parse_parent_ids(cell: str) -> list[str]:
    parents: list[str] = []
    seen: set[str] = set()
    for part in cell.split(";"):
        parent = part.strip()
        if parent == "" or parent in seen:
            continue
        seen.add(parent)
        parents.append(parent)
    return parents


def _row_is_blank(row: tuple[str, ...]) -> bool:
    return all(cell.strip() == "" for cell in row)


def _ask_index(
    io: PromptIO,
    prompt: str,
    headers: list[str],
    *,
    optional: bool,
) -> int | None:
    bound = len(headers)
    while True:
        answer = io.ask(f"{prompt} [1-{bound}]: ").strip()
        if answer == "":
            if optional:
                return None
            io.tell("A value is required.")
            continue
        parsed = _parse_one_index(answer, bound)
        if parsed is None:
            io.tell(f"Enter a number between 1 and {bound}.")
            continue
        return parsed


def _ask_index_list(io: PromptIO, prompt: str, headers: list[str]) -> list[int]:
    bound = len(headers)
    while True:
        answer = io.ask(f"{prompt}: ").strip()
        if answer == "":
            return []
        indexes: list[int] = []
        valid = True
        for part in answer.split(","):
            parsed = _parse_one_index(part.strip(), bound)
            if parsed is None:
                valid = False
                break
            if parsed not in indexes:
                indexes.append(parsed)
        if valid:
            return indexes
        io.tell(f"Enter comma-separated numbers between 1 and {bound}.")


def _parse_one_index(answer: str, bound: int) -> int | None:
    if not answer.isdigit():
        return None
    value = int(answer)
    if value < 1 or value > bound:
        return None
    return value - 1


def _ask_status_order(io: PromptIO, found: list[str]) -> list[str]:
    default = ", ".join(found)
    while True:
        suffix = f" [{default}]" if default else ""
        answer = io.ask(
            "Order statuses least-severe to most-severe (comma-separated)."
            f"{suffix}: "
        ).strip()
        raw = answer if answer else default
        ordered = [part.strip() for part in raw.split(",") if part.strip()]
        if not ordered:
            io.tell("Enter at least one status id.")
            continue
        seen: set[str] = set()
        unique: list[str] = []
        for item in ordered:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique


def _ask_line(io: PromptIO, prompt: str, default: str) -> str:
    answer = io.ask(prompt).strip()
    return answer if answer else default
