"""Exceptions raised by the converter pipeline."""


class TreeViewerError(Exception):
    """Base error for converter failures."""


class MappingError(TreeViewerError):
    """Raised when column mapping or interactive prompts are invalid."""


class GraphValidationError(TreeViewerError):
    """Raised when the graph violates a documented invariant."""


class CycleError(GraphValidationError):
    """Raised when hierarchical links contain a cycle."""
