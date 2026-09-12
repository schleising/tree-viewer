"""Graph invariants from the design document."""

from treeviewer.errors import CycleError, GraphValidationError
from treeviewer.model import GraphDocument, Link, Node, Status


def validate(document: GraphDocument) -> GraphDocument:
    """Check document invariants and return `document` unchanged.

    Args:
        document: Normalised graph.

    Returns:
        The same document if it is valid.

    Raises:
        GraphValidationError: If an invariant fails.
        CycleError: If the directed links contain a cycle.
    """
    _validate_statuses(document.statuses)
    node_ids = _validate_nodes(document.nodes)
    _validate_links(document.links, node_ids)
    _validate_child_ids(document.nodes, document.links)
    _validate_node_statuses(document.nodes, document.statuses)
    _detect_cycle(document.nodes, document.links)
    return document


def _validate_statuses(statuses: list[Status]) -> None:
    if not statuses:
        raise GraphValidationError("Status catalogue must have at least one entry")
    seen: set[str] = set()
    for index, status in enumerate(statuses):
        if status.id in seen:
            raise GraphValidationError(f"Duplicate status id: {status.id}")
        seen.add(status.id)
        if status.severity != index:
            raise GraphValidationError(
                f"Status {status.id!r} severity {status.severity} does not match order {index}"
            )


def _validate_nodes(nodes: list[Node]) -> set[str]:
    ids: set[str] = set()
    for node in nodes:
        if node.id == "":
            raise GraphValidationError("Node id must be non-empty")
        if node.title == "":
            raise GraphValidationError(f"Node {node.id!r} has an empty title")
        if node.id in ids:
            raise GraphValidationError(f"Duplicate node id: {node.id}")
        ids.add(node.id)
    return ids


def _validate_links(links: list[Link], node_ids: set[str]) -> None:
    seen: set[tuple[str, str]] = set()
    for link in links:
        if link.from_id == link.to_id:
            raise GraphValidationError(f"Self-link is not allowed: {link.from_id}")
        if link.from_id not in node_ids:
            raise GraphValidationError(f"Link refers to missing parent: {link.from_id}")
        if link.to_id not in node_ids:
            raise GraphValidationError(f"Link refers to missing child: {link.to_id}")
        edge = (link.from_id, link.to_id)
        if edge in seen:
            raise GraphValidationError(f"Duplicate link: {link.from_id} -> {link.to_id}")
        seen.add(edge)


def _validate_child_ids(nodes: list[Node], links: list[Link]) -> None:
    expected: dict[str, list[str]] = {node.id: [] for node in nodes}
    for link in links:
        expected[link.from_id].append(link.to_id)
    for node in nodes:
        if node.child_ids != expected.get(node.id, []):
            raise GraphValidationError(f"childIds do not match links for {node.id}")


def _validate_node_statuses(nodes: list[Node], statuses: list[Status]) -> None:
    ids = {status.id for status in statuses}
    for node in nodes:
        if node.status not in ids:
            raise GraphValidationError(f"Node {node.id} has unknown status {node.status!r}")
        if node.rollup_status not in ids:
            raise GraphValidationError(
                f"Node {node.id} has unknown roll-up status {node.rollup_status!r}"
            )


def _detect_cycle(nodes: list[Node], links: list[Link]) -> None:
    children: dict[str, list[str]] = {node.id: [] for node in nodes}
    for link in links:
        children[link.from_id].append(link.to_id)

    white, gray, black = 0, 1, 2
    state = {node.id: white for node in nodes}

    def visit(node_id: str, stack: list[str]) -> None:
        state[node_id] = gray
        path = [*stack, node_id]
        for child in children[node_id]:
            if state[child] == gray:
                cycle = [*path[path.index(child) :], child]
                raise CycleError("Cycle in links: " + " -> ".join(cycle))
            if state[child] == white:
                visit(child, path)
        state[node_id] = black

    for node in nodes:
        if state[node.id] == white:
            visit(node.id, [])
