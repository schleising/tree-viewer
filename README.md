# Tree Viewer

Web viewer for hierarchical items as status-coloured nodes. A Python converter reads one CSV file and writes `graph.json`. The static viewer fetches that JSON, starts collapsed at the roots, and expands a node when you click its chevron.

## Convert a CSV

```bash
python -m treeviewer convert examples/four-level/items.csv \
    --map examples/four-level/items.map.json \
    --title "Delivery programmes" \
    --out web/graph.json
```

Without `--map`, the converter lists the CSV columns and asks which ones are the item, status, links, data fields, and source URL, then asks you to order and colour the statuses.

```bash
python -m treeviewer convert path/to/items.csv \
    --title "My tree" \
    --out web/graph.json \
    --save-map path/to/items.map.json
```

## View the tree

The viewer cannot open `index.html` from `file://`. Serve the `web` folder:

```bash
python -m http.server --directory web 8000
```

Then open http://localhost:8000

- Chevron expands or collapses that node only
- **Own status** / **Roll-up** switches colour for the whole tree
- **Open source** opens the item URL in a new tab
- Drag the background to pan; scroll to zoom; **Reset view** fits the current nodes

## Development

```bash
python -m pip install -e ".[dev,docs]"
python -m pytest
```

Example data lives in `examples/simple` and `examples/four-level`.
