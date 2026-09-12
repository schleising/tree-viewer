"""Turn mapped records into a graph document."""

from treeviewer.errors import GraphValidationError
from treeviewer.model import (
    ColumnMap,
    DocumentMeta,
    GraphDocument,
    Link,
    Node,
    RawRecord,
    SCHEMA_VERSION,
    ColorMode,
)


def normalize(
    records: list[RawRecord],
    mapping: ColumnMap,
    *,
    title: str,
    description: str = "",
    color_mode: ColorMode = "own",
    strict: bool = False,
) -> GraphDocument:
    """Build a graph document from mapped records.

    Applies the status fallback and drops invalid source URLs unless
    `strict` is true.

    Args:
        records: Rows bound from the CSV.
        mapping: Column map including the status catalogue.
        title: Document title.
        description: Optional header subtitle.
        color_mode: Initial viewer colour mode.
        strict: Reject unknown statuses and invalid URLs.

    Returns:
        An unvalidated document. `rollup_status` matches `status`.

    Raises:
        GraphValidationError: If `strict` is set and a value is invalid,
            or the catalogue is unusable.
    """
    statuses = mapping.statuses
    fallback = mapping.status_fallback
    if not statuses or fallback is None:
        raise GraphValidationError("Column map is missing a status catalogue")
    status_ids = {item.id for item in statuses}

    nodes: list[Node] = []
    links: list[Link] = []
    seen_edges: set[tuple[str, str]] = set()

    for record in records:
        status = _resolve_status(record.status, status_ids, fallback, strict=strict)
        source_url = _resolve_source_url(record.source_url, strict=strict)
        nodes.append(
            Node(
                id=record.id,
                title=record.title,
                subtitle=record.subtitle,
                status=status,
                rollup_status=status,
                source_url=source_url,
                data=record.data,
                child_ids=[],
            )
        )
        for parent_id in record.parent_ids:
            edge = (parent_id, record.id)
            if parent_id == record.id:
                raise GraphValidationError(f"Self-link is not allowed: {record.id}")
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            links.append(Link(from_id=parent_id, to_id=record.id))

    child_ids = _child_ids_from_links(nodes, links)
    nodes = [
        node.model_copy(update={"child_ids": child_ids.get(node.id, [])})
        for node in nodes
    ]
    return GraphDocument(
        schema_version=SCHEMA_VERSION,
        meta=DocumentMeta(
            title=title,
            description=description,
            default_color_mode=color_mode,
            display_fields=list(mapping.data),
        ),
        statuses=list(statuses),
        nodes=nodes,
        links=links,
    )


def _resolve_status(
    raw: str | None,
    status_ids: set[str],
    fallback: str,
    *,
    strict: bool,
) -> str:
    if raw is None or raw == "":
        if strict:
            raise GraphValidationError("Missing status in strict mode")
        return fallback
    if raw in status_ids:
        return raw
    if strict:
        raise GraphValidationError(f"Unknown status {raw!r}")
    return fallback


def _resolve_source_url(raw: str | None, *, strict: bool) -> str | None:
    if raw is None or raw == "":
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if strict:
        raise GraphValidationError(f"Invalid source URL: {raw}")
    return None


def _child_ids_from_links(nodes: list[Node], links: list[Link]) -> dict[str, list[str]]:
    """Build a node-id lookup of outgoing children in link order."""
    children: dict[str, list[str]] = {node.id: [] for node in nodes}
    for link in links:
        if link.from_id not in children:
            children[link.from_id] = []
        children[link.from_id].append(link.to_id)
    return children
