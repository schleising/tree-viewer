"""Command-line interface for the converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from treeviewer.adapters.csv_adapter import adapter_for
from treeviewer.convert import convert_and_write, resolve_mapping
from treeviewer.errors import MappingError, TreeViewerError
from treeviewer.io import StreamPrompt
from treeviewer.mapping import load_column_map, save_column_map
from treeviewer.model import ColorMode, ColumnMap, Status, TabularSource, with_ordered_severity
from treeviewer.model import neutral_status


def main(argv: list[str] | None = None) -> int:
    """Run the `treeviewer` command.

    Args:
        argv: Argument list without the program name. Defaults to `sys.argv[1:]`.

    Returns:
        Process exit code. `0` on success, `1` on a converter error, `2` on
        usage errors.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "convert":
        parser.print_help()
        return 2
    try:
        _run_convert(args)
    except (TreeViewerError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="treeviewer",
        description="Convert a hierarchical CSV into graph JSON for the web viewer.",
    )
    sub = parser.add_subparsers(dest="command")
    convert = sub.add_parser("convert", help="Convert a CSV file to graph.json")
    convert.add_argument("csv", type=Path, help="Input CSV file")
    convert.add_argument("--out", type=Path, default=Path("web/graph.json"), help="Output JSON path")
    convert.add_argument("--title", default="", help="Document title")
    convert.add_argument("--description", default="", help="Document description")
    convert.add_argument(
        "--color-mode",
        dest="color_mode",
        choices=("own", "rollup"),
        default="own",
        help="Initial colour mode",
    )
    convert.add_argument("--map", dest="map_path", type=Path, help="Saved column map JSON")
    convert.add_argument("--save-map", dest="save_map", type=Path, help="Write the chosen map")
    convert.add_argument("--id-column", dest="id_column", help="Item id column header")
    convert.add_argument("--title-column", dest="title_column", help="Item title column header")
    convert.add_argument("--status-column", dest="status_column", help="Status column header")
    convert.add_argument("--links-column", dest="links_column", help="Parent-id column header")
    convert.add_argument(
        "--source-url-column",
        dest="source_url_column",
        help="Source URL column header",
    )
    convert.add_argument(
        "--data-columns",
        dest="data_columns",
        help="Comma-separated extra field headers",
    )
    convert.add_argument(
        "--statuses-json",
        dest="statuses_json",
        type=Path,
        help="Status catalogue JSON array",
    )
    convert.add_argument("--status-fallback", dest="status_fallback", help="Fallback status id")
    convert.add_argument("--delimiter", default=",", help="CSV delimiter")
    convert.add_argument("--adapter", default=None, help="Source adapter name")
    convert.add_argument("--strict", action="store_true", help="Fail on unknown status or URL")
    convert.add_argument("--rollup", default="worst_wins", help="Roll-up strategy")
    return parser


def _run_convert(args: argparse.Namespace) -> None:
    csv_path: Path = args.csv
    table = adapter_for(csv_path, args.adapter).read(csv_path, delimiter=args.delimiter)
    mapping = _mapping_from_args(args, table)
    title = args.title or csv_path.stem
    color_mode: ColorMode = args.color_mode
    document = convert_and_write(
        csv_path,
        args.out,
        mapping,
        title=title,
        description=args.description,
        color_mode=color_mode,
        delimiter=args.delimiter,
        adapter=args.adapter,
        strict=args.strict,
        rollup=args.rollup,
    )
    print(f"Wrote {args.out} ({len(document.nodes)} nodes, {len(document.links)} links)")


def _mapping_from_args(args: argparse.Namespace, table: TabularSource) -> ColumnMap:
    if args.map_path is not None:
        mapping = load_column_map(args.map_path)
        if args.save_map is not None:
            save_column_map(mapping, args.save_map)
        return mapping

    if args.id_column:
        mapping = _mapping_from_columns(args)
        if args.save_map is not None:
            save_column_map(mapping, args.save_map)
        return mapping

    io = StreamPrompt(sys.stdin, sys.stdout) if sys.stdin.isatty() else None
    return resolve_mapping(table, map_path=None, io=io, save_map_path=args.save_map)


def _mapping_from_columns(args: argparse.Namespace) -> ColumnMap:
    data_columns = (
        [part.strip() for part in args.data_columns.split(",") if part.strip()]
        if args.data_columns
        else []
    )
    statuses = _load_statuses(args.statuses_json) if args.statuses_json else []
    if not statuses:
        if args.status_column is not None:
            raise MappingError("A --statuses-json file is required when --status-column is set")
        statuses = [neutral_status()]
    statuses = with_ordered_severity(statuses)
    fallback = args.status_fallback or statuses[-1].id
    return ColumnMap(
        id=args.id_column,
        title=args.title_column or args.id_column,
        status=args.status_column,
        links=args.links_column,
        data=data_columns,
        source_url=args.source_url_column,
        statuses=statuses,
        status_fallback=fallback,
    )


def _load_statuses(path: Path) -> list[Status]:
    try:
        return TypeAdapter(list[Status]).validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise MappingError(f"Invalid statuses JSON {path}: {exc}") from exc
