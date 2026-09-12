"""Status roll-up strategies."""

from typing import Protocol

from treeviewer.errors import GraphValidationError
from treeviewer.model import GraphDocument, Node, Status


class RollupStrategy(Protocol):
    """Computes `rollup_status` on every node."""

    def compute(self, document: GraphDocument) -> GraphDocument:
        """Return a copy of `document` with roll-up statuses filled in."""
        ...


class WorstWinsRollup:
    """Assign each node the highest-severity status in its subtree."""

    def compute(self, document: GraphDocument) -> GraphDocument:
        """Compute worst-wins roll-up for every node.

        A node's roll-up is the maximum of its own status and the roll-up
        of every descendant.

        Args:
            document: Validated graph.

        Returns:
            A new document with updated `rollup_status` fields.

        Raises:
            GraphValidationError: If a node status is not in the catalogue.
        """
        by_id: dict[str, Status] = {status.id: status for status in document.statuses}
        children: dict[str, list[str]] = {node.id: list(node.child_ids) for node in document.nodes}
        node_by_id: dict[str, Node] = {node.id: node for node in document.nodes}
        memo: dict[str, str] = {}

        def visit(node_id: str) -> str:
            if node_id in memo:
                return memo[node_id]
            node = node_by_id[node_id]
            worst = _require_status(by_id, node.status, node_id)
            for child_id in children[node_id]:
                child_status = _require_status(by_id, visit(child_id), child_id)
                if child_status.severity > worst.severity:
                    worst = child_status
            memo[node_id] = worst.id
            return worst.id

        for node in document.nodes:
            visit(node.id)

        rolled = [
            node.model_copy(update={"rollup_status": memo[node.id]})
            for node in document.nodes
        ]
        return document.model_copy(update={"nodes": rolled})


def strategy_for(name: str) -> RollupStrategy:
    """Return a named roll-up strategy.

    Args:
        name: Strategy id. Only `worst_wins` is supported in v1.

    Returns:
        The matching strategy.

    Raises:
        GraphValidationError: If `name` is unknown.
    """
    if name == "worst_wins":
        return WorstWinsRollup()
    raise GraphValidationError(f"Unknown roll-up strategy: {name}")


def _require_status(by_id: dict[str, Status], status_id: str, node_id: str) -> Status:
    status = by_id.get(status_id)
    if status is None:
        raise GraphValidationError(f"Node {node_id} has unknown status {status_id!r}")
    return status
