# Tree Viewer — Design Document

A web-based graphical relationship viewer for hierarchical data. Items are rendered as status-coloured nodes. The graph starts collapsed at the roots; clicking a node’s expand control reveals its child links. A Python converter turns a single CSV file into a shared JSON document that the viewer consumes.

## 1. Goals

- Show hierarchical relationships as a graphical tree of nodes, not as a nested list.
- Start with every link collapsed so only top-level nodes are visible.
- Expand or collapse a node’s outgoing links with a click on its expand control.
- Colour each node from either the node’s own status or a roll-up of its descendants.
- Let each item optionally link back to its source (for example a Jira ticket) in a new tab.
- Keep a single JSON contract between data preparation and the web view.
- Provide an extensible Python converter that reads one CSV (item, data, status, and links on each row) and emits that JSON.
- Let the user define the status list (labels, colours, and severity order) at CSV import time, and write that catalogue into the JSON. Different data sources may use different statuses and a different order.

## 2. Non-goals (v1)

- Editing, creating, or deleting nodes in the browser.
- Live collaboration or a server-side database.
- General graph editing (cycles, undirected meshes, weighted networks).
- Authentication, multi-user access, or hosted multi-tenancy.
- Automatic layout of very large graphs (thousands of simultaneously expanded nodes).

Cycles in the link data are rejected at convert time. Multiple parents (a DAG) are allowed: a node with several parents is drawn **once**, with multiple inbound edges.

## 3. Architecture

```
Single CSV               Python converter              Static web viewer
──────────               ────────────────              ─────────────────
items.csv  ──►  prompt for columns  ──►  graph.json  ──►  HTML/CSS/JS
            prompt for status list         ▲              (fetch)
            adapter → graph model          │
            validate → roll-up             └── ./graph.json
```

Two processes, one contract:

| Layer | Responsibility |
| --- | --- |
| Converter | Read one CSV, ask which columns are item / data / status / links / source URL, ask the user to define the status catalogue and its order, validate IDs and links, compute roll-up statuses, write `graph.json`. |
| Viewer | Fetch JSON, lay out nodes and edges, handle expand/collapse, apply colour mode from the document’s `statuses` list, open source URLs in a new tab. |

The viewer never reads CSV. The converter never renders UI. Anything that can produce the JSON schema can feed the viewer later (spreadsheets, APIs, other scripts) without changing the front end.

## 4. User experience

### 4.1 First paint

The view shows only **root** nodes: items with no incoming hierarchical link. Every expandable node is collapsed. Roots occupy the first column. No child nodes or edges are drawn.

### 4.2 Expand and collapse

- A node with children shows an expand control (chevron or “+N”).
- **Only the chevron** expands or collapses. Clicks on the node body, text, or source link do not toggle.
- Expanding draws child nodes in the next column and orthogonal edges from parent to each child.
- Collapsing hides that subtree. Descendants that were expanded are forgotten; the next expand starts collapsed again.
- Expanding one node does not expand siblings or cousins.
- Nodes with no children have no expand control.

This is per-node expansion, not a global accordion. Several branches can be open at once.

### 4.3 Nodes

Each item is a compact graphical node that can show text and a status colour. Implementation may use HTML/CSS, SVG, canvas, or a mix — whichever keeps text readable, hit-testing simple, and edges easy to draw. HTML nodes with an SVG edge layer is a good default; it is not a requirement.

| Region | Content |
| --- | --- |
| Title | Required. Primary label. |
| Subtitle | Optional. Short secondary line (id, owner, type). |
| Body | Extra fields chosen by the user during CSV import (see §7.2). |
| Status chip | Status label, always shown as text so colour is not the only signal. |
| Accent | Left border and/or tint from the active colour mode. |
| Source link | Optional. Opens the item’s source (Jira, wiki, …) in a new browser tab. |
| Expand control | Chevron only; visible only when the node has children. |

Nodes have a fixed minimum width and wrap long text. They do not grow unbounded.

The source link uses `target="_blank"` and `rel="noopener noreferrer"`. It is a distinct control from the chevron so opening Jira never expands the tree.

### 4.4 Colour modes

A toolbar toggle switches the whole view:

| Mode | Node colour comes from |
| --- | --- |
| **Own status** | The node’s declared `status`. |
| **Roll-up** | `rollupStatus`, computed from the subtree (see §6). |

Changing mode does not change expand state. A legend lists every entry in the document’s `statuses` array, in that array’s order. The viewer does not have a built-in status list.

### 4.5 Navigation

- Pan by dragging the canvas background.
- Zoom with trackpad / wheel (and optional +/− controls).
- A “Reset view” action fits the currently visible nodes.
- Optional later: search/filter by title. Not required for v1.

## 5. Canonical JSON

This is the only format the viewer understands. Version the document so the viewer can reject unknown majors.

```json
{
  "schemaVersion": "1.0",
  "meta": {
    "title": "Q3 delivery tree",
    "description": "Optional subtitle shown in the viewer header.",
    "defaultColorMode": "own",
    "displayFields": ["owner", "updated"]
  },
  "statuses": [
    { "id": "Done",         "label": "Done",         "color": "#2e7d32", "severity": 0 },
    { "id": "To Do",        "label": "To Do",        "color": "#1565c0", "severity": 1 },
    { "id": "In Progress",  "label": "In Progress",  "color": "#f9a825", "severity": 2 },
    { "id": "Blocked",      "label": "Blocked",      "color": "#c62828", "severity": 3 }
  ],
  "nodes": [
    {
      "id": "epics",
      "title": "Epics",
      "subtitle": "Portfolio",
      "status": "In Progress",
      "rollupStatus": "Blocked",
      "sourceUrl": "https://jira.example.com/browse/PROG-1",
      "data": { "owner": "Alex", "updated": "2026-09-01" },
      "childIds": ["e1", "e2"]
    }
  ],
  "links": [
    { "from": "epics", "to": "e1" },
    { "from": "epics", "to": "e2" }
  ]
}
```

### 5.1 Field rules

**Document**

| Field | Type | Notes |
| --- | --- | --- |
| `schemaVersion` | string | Semver. Viewer accepts `1.x`. |
| `meta.title` | string | Header title. |
| `meta.defaultColorMode` | `"own"` \| `"rollup"` | Initial toggle. Default `"own"`. |
| `meta.displayFields` | string[] | Keys from `nodes[].data` to show on the node. Chosen at import time. Empty means no extra body fields. |
| `statuses` | array | User-defined catalogue from CSV import. At least one entry. Array order is the severity order (first = least severe). The viewer uses this list only; it has no built-in statuses. |
| `nodes` | array | Every item that can appear as a node. |
| `links` | array | Directed parent → child edges. |

**Status**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable key referenced by nodes. Usually the raw CSV value. |
| `label` | string | Shown on the chip and legend. Defaults to `id` if the user does not set a different label. |
| `color` | string | CSS colour (`#rrggbb` recommended). Chosen at import time. |
| `severity` | integer ≥ 0 | Higher means worse. Used only for roll-up. Matches the catalogue order (index `0` for the first entry). |

**Node**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Unique. Used as the expand key. |
| `title` | string | Required, non-empty. |
| `subtitle` | string? | Optional. |
| `status` | string | Must match a `statuses[].id`. Blank or unrecognised CSV values use the fallback status chosen at import. |
| `rollupStatus` | string | Always written by the converter. Always a `statuses[].id`. |
| `sourceUrl` | string? | Absolute http(s) URL to the source item. Omitted when the row has none. |
| `data` | object | Extra fields selected during import. Unknown keys are passed through. |
| `childIds` | string[] | Convenience index of outgoing links, same order as `links`. Viewer may recompute from `links`. |

**Link**

| Field | Type | Notes |
| --- | --- | --- |
| `from` | string | Parent node id. |
| `to` | string | Child node id. |
| `label` | string? | Reserved; unused in v1 layout. |

Roots are nodes that never appear as `links[].to`. Isolated nodes (no links at all) are roots.

### 5.2 Invariants the converter must enforce

1. Node ids are unique and non-empty.
2. Every `links[].from` and `links[].to` refers to an existing node.
3. Self-links (`from == to`) are rejected.
4. Duplicate links are collapsed to one.
5. The directed graph of links is acyclic.
6. `statuses` is non-empty, ids are unique, and `severity` values are unique and increase with array order (first entry is least severe).
7. Every `status` / `rollupStatus` is a `statuses[].id` (after applying the import fallback).
8. `childIds` matches the `from` → `to` links for that node.
9. If `sourceUrl` is present, it is an `http://` or `https://` URL; other values are dropped (or rejected in `--strict` mode).
10. Every `meta.displayFields` entry exists as a key on at least one node’s `data`, or is accepted as an intentionally empty column.

## 6. Status colour and roll-up

### 6.1 Own status

Taken from the source row and matched to the user-defined catalogue written into `statuses`. Blank cells and values that are not in the catalogue become the fallback status the user chose at import (see §7.2).

The viewer never invents statuses. Chip text and colour always come from `statuses[]` in the loaded JSON.

### 6.2 Roll-up (worst-wins)

Severity is the order of `statuses` in the JSON: the first entry is least severe, the last is most severe. `severity` on each entry mirrors that order.

For each node, `rollupStatus` is the status with the **highest severity** among:

- the node’s own status, and
- the roll-up status of every descendant (not only direct children).

Leaves therefore have `rollupStatus == status`. A parent whose own status is “In Progress” with one “Blocked” grandchild is “Blocked” in roll-up mode, if “Blocked” is later in the catalogue.

This is computed once in the converter (post-order over the DAG) and stored on every node so the viewer does not re-implement the rule. If a later aggregator is added (majority, custom Python hook), the converter writes a different `rollupStatus`; the viewer still just paints whatever id it is given.

### 6.3 Accessibility

Colour is paired with the status label on every node. Do not rely on hue alone. Suggested import colours should have sufficient contrast on a light node background; the user may override them.

## 7. CSV input and the Python converter

### 7.1 Single input file

One UTF-8 CSV with a header row. Each row is one item. Item identity, display data, status, hierarchical links, and an optional source URL all live on that row.

```csv
Key,Summary,Status,Parent,Owner,Updated,URL
PROG-1,Programme,In Progress,,Sam,2026-09-01,https://jira.example.com/browse/PROG-1
WS-A,Workstream A,Done,PROG-1,Alex,2026-09-02,https://jira.example.com/browse/WS-A
WS-B,Workstream B,Blocked,PROG-1,Jo,2026-09-03,https://jira.example.com/browse/WS-B
VEN-1,Vendor,Blocked,WS-B,Jo,2026-09-04,https://jira.example.com/browse/VEN-1
```

There is no separate links file or status catalogue file. Status values come from the chosen status column; the **meaning, colours, and order** of those values are defined by the user during import and written into `graph.json` as `statuses` (see §7.2). Another CSV (for example a different Jira project or a spreadsheet with RAG ratings) will typically produce a different `statuses` list.

**Links column.** The chosen links column holds the parent item id(s). Empty means this row is a root. Several parents may be listed as a semicolon-separated list (`PROG-1;PROG-2`). Each parent id becomes a `{ from: parent, to: this row's id }` link.

### 7.2 Interactive column mapping

Column names are not assumed. After reading the header, the converter lists the columns and asks which ones to use.

| Role | How many | Purpose |
| --- | --- | --- |
| **Item** | one, or two | Identity and title. If one column is chosen it is both `id` and `title`. If two are chosen, the first is `id` and the second is `title` (for example Jira `Key` + `Summary`). |
| **Status** | one, optional | Node `status`. If a column is chosen, the user then defines the catalogue for its values (§7.2). If skipped, the converter writes a single neutral status and assigns every node to it. |
| **Links** | one, optional | Parent id(s) for the hierarchy. If skipped, every node is a root. |
| **Data** | zero or more | Extra columns copied into `nodes[].data` and listed in `meta.displayFields`. These are the fields shown on the node body. |
| **Source URL** | one, optional | Absolute URL opened in a new tab. If skipped, nodes have no source link. |

Prompt shape (TTY):

```text
Columns in items.csv:
  1) Key
  2) Summary
  3) Status
  4) Parent
  5) Owner
  6) Updated
  7) URL

Item id column [1-7]: 1
Item title column (blank = same as id): 2
Status column (blank = none): 3
Links / parent column (blank = none): 4
Data columns to show on each node (comma-separated, blank = none): 5,6
Source URL column (blank = none): 7
```

**Status catalogue.** If a status column was chosen, the converter collects the distinct values from that column and asks the user to define the list that will be stored in `graph.json`. The user sets order (least severe first), optional labels, colours, and a fallback for blank or unexpected values. They may add statuses that do not appear in this file yet, and they may omit a found value only if they also set a fallback that will absorb it.

```text
Distinct values in Status: Done, To Do, In Progress, Blocked

Order statuses least-severe to most-severe (comma-separated).
You may add values that do not appear yet.
[Done, To Do, In Progress, Blocked]: Done, To Do, In Progress, Blocked

Label for 'Done' [Done]:
Colour for 'Done' [#2e7d32]:
Label for 'To Do' [To Do]:
Colour for 'To Do' [#1565c0]:
Label for 'In Progress' [In Progress]:
Colour for 'In Progress' [#f9a825]:
Label for 'Blocked' [Blocked]:
Colour for 'Blocked' [#c62828]:

Fallback status for blank or unrecognised values [Blocked]: Blocked
```

Suggested colours are offered in order so the user can accept them with Enter. The saved catalogue is written as `statuses` in `graph.json` and also into the map file so a later `--map` run does not re-prompt.

Rules:

- A column may be used in more than one role only where that is useful (for example `Key` as id and also in data). The links and status columns are not shown as body fields unless the user also lists them under data.
- Answers are validated against the header index; out-of-range or non-integer input is re-prompted.
- At least an item id column is required.
- The status catalogue must have unique ids and at least one entry. The fallback must be one of those ids.
- Duplicate ids, dangling parent ids, and cycles are reported after mapping, not during the prompt.

### 7.3 Saved mapping and CLI

Interactive prompts are the default. A mapping can be written and reused so batch runs do not ask again.

```text
python -m treeviewer convert data/items.csv \
    --title "Q3 delivery tree" \
    --color-mode own \
    --out web/graph.json \
    --save-map data/items.map.json
```

```text
python -m treeviewer convert data/items.csv \
    --map data/items.map.json \
    --out web/graph.json
```

Example `items.map.json`:

```json
{
  "id": "Key",
  "title": "Summary",
  "status": "Status",
  "links": "Parent",
  "data": ["Owner", "Updated"],
  "sourceUrl": "URL",
  "statuses": [
    { "id": "Done", "label": "Done", "color": "#2e7d32", "severity": 0 },
    { "id": "To Do", "label": "To Do", "color": "#1565c0", "severity": 1 },
    { "id": "In Progress", "label": "In Progress", "color": "#f9a825", "severity": 2 },
    { "id": "Blocked", "label": "Blocked", "color": "#c62828", "severity": 3 }
  ],
  "statusFallback": "Blocked"
}
```

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--map path` | Load a previously saved column map; skip prompts. Required when stdin is not a TTY. |
| `--save-map path` | Write the chosen map after a successful prompt (or copy of `--map`). |
| `--id-column`, `--title-column`, `--status-column`, `--links-column`, `--source-url-column`, `--data-columns` | Non-interactive equivalents of the column prompts. |
| `--statuses-json path` | Non-interactive status catalogue (same shape as `statuses` in the map file), plus `--status-fallback`. |
| `--delimiter ';'` | Non-comma CSV. |
| `--strict` | Fail on unrecognised status values or invalid `sourceUrl` instead of using the fallback / dropping. |

### 7.4 Extensibility

The converter is a pipeline of typed stages, not a single script with hardcoded column names.

```
SourceAdapter.read()  →  list[RawRecord]
ColumnMapper.bind()   →  list[RawRecord]   # from prompts or --map
StatusCatalogue.bind() →  list[Status]     # from prompts or --map; written to graph.json
Normalizer.normalize()  →  GraphDocument
Validator.validate()  →  GraphDocument
Rollup.compute()  →  GraphDocument
JsonWriter.write()
```

| Extension point | How to extend |
| --- | --- |
| New file format (xlsx, JSON Lines) | Implement `SourceAdapter` and register it by suffix / `--adapter`. The same column-mapping step still runs. |
| Odd CSV layouts | Interactive map, saved `--map`, or a small adapter that yields `RawRecord`s. |
| Extra node fields | User-selected data columns land in `data` and `meta.displayFields`. |
| Custom roll-up | Implement `RollupStrategy` (`worst_wins` is the default). Select with `--rollup worst_wins`. |
| Status catalogues | Defined at import and stored in `graph.json`. Reuse via the map file; a different source gets a different list. |

`RawRecord` is a typed dict: `{ id, title, subtitle?, status?, parent_ids?, source_url?, data }`. Adapters must produce that shape; they must not write JSON themselves.

Keep v1 on the standard library (`csv`, `json`, `argparse`, `dataclasses`). Add Pydantic or a schema package only if validation becomes painful.

## 8. Viewer design

### 8.1 Runtime

Static files. No application server.

```
web/
  index.html
  styles.css
  app.js
  graph.json          # produced by the converter; gitignored or example-only
```

v1 loads data with `fetch('./graph.json')`. Serve the folder with any static server (`python -m http.server`). Opening `index.html` via `file://` will not work.

### 8.2 Layout model

**Left to right.** Each hierarchy level occupies a single column. Roots in column 0, children of expanded roots in column 1, and so on.

1. Collect the visible set: all roots, plus children of every expanded node.
2. Assign each visible node a column = one plus the maximum column of its visible parents (roots = 0). A node with several parents sits in the column after the rightmost visible parent.
3. Pack nodes within a column to avoid overlap, using measured node height.
4. Draw edges as orthogonal polylines (elbow connectors) from parent to child.

A node is drawn **once**. If it has multiple visible parents, several inbound edges meet that same node. Expand/collapse is keyed by node id, not by parent path.

Only **visible** nodes are laid out. Collapsed children occupy no space. Re-layout runs after every expand/collapse.

Implementation may use:

- HTML/CSS for nodes and SVG for edges (good default: selectable text, native `<a>` for source URLs).
- Pure SVG, or canvas, if that proves simpler for pan/zoom.

Avoid force-directed layouts; they fight hierarchy and collapse.

### 8.3 Interaction state

Viewer state is not persisted in v1:

```ts
{
  colorMode: "own" | "rollup",   // from meta.defaultColorMode
  expanded: Set<nodeId>,
  pan: { x, y },
  zoom: number
}
```

`expanded` stores node ids. Expanding a shared child from any inbound edge shows the same node and the same outgoing subtree.

### 8.4 Rendering a node colour

```
activeStatus = colorMode === "own" ? node.status : node.rollupStatus
color        = statuses[activeStatus].color
label        = statuses[activeStatus].label
```

Apply `color` to the left accent bar and a low-opacity wash. The chip text is `label`.

### 8.5 Source links

If `node.sourceUrl` is set, the node shows a control (icon and/or “Open”) that:

- uses an `<a href="…">` (or equivalent) with `target="_blank"` and `rel="noopener noreferrer"`;
- is excluded from the chevron hit target;
- is omitted entirely when `sourceUrl` is absent.

The viewer does not validate the URL beyond what the converter already stored.

### 8.6 Empty and error states

| Condition | Viewer behaviour |
| --- | --- |
| Missing `graph.json` | Banner: file not found; remind to run the converter. |
| Unsupported `schemaVersion` | Banner: incompatible data. |
| Zero nodes | Empty view with the document title. |
| Validation issues already rejected | Converter exits non-zero; viewer is not given partial files. |

## 9. Proposed repository layout

```
tree-viewer/
  docs/DESIGN.md
  README.md
  LICENSE
  pyproject.toml
  src/treeviewer/
    __init__.py
    __main__.py          # python -m treeviewer
    cli.py
    model.py             # dataclasses for GraphDocument
    adapters/
      base.py
      csv_adapter.py
    mapping.py           # interactive + file-based column map and status catalogue
    normalize.py
    validate.py
    rollup.py
    write.py
  tests/
    test_csv_adapter.py
    test_mapping.py
    test_validate.py
    test_rollup.py
  web/
    index.html
    styles.css
    app.js
  examples/
    simple/
      items.csv
      items.map.json     # saved column map for non-interactive tests
      graph.json         # checked-in golden file
  data/                  # local inputs; gitignored except examples
```

## 10. Implementation sequence

1. **JSON schema + dataclasses** — `model.py` and a golden `examples/simple/graph.json`.
2. **CSV adapter + column mapping** — interactive prompts (including the status catalogue), `--map` / `--save-map`, unit tests with a saved map (no TTY).
3. **Validation + roll-up** — cycles, dangling parents, worst-wins on trees and a small DAG; golden values in the example JSON.
4. **Static viewer** — fetch JSON, render root nodes, chevron expand/collapse, single node with multiple inbound edges, own vs roll-up toggle, source links, pan/zoom.
5. **Polish** — legend, reset view, README usage.

## 11. Testing

| Area | Cases |
| --- | --- |
| Mapping | Prompt answers (tested via injected input), `--map` file, one-column item vs id+title, multi-select data columns, missing optional roles, status order / labels / colours / fallback. |
| Adapter | Extra columns ignored unless selected, semicolon parent lists, empty parent = root, source URL kept / dropped. |
| Validation | Duplicate ids, dangling links, self-links, cycles, status not in the user catalogue (strict vs fallback), invalid URL, empty or duplicate status catalogue. |
| Roll-up | Leaf equality, worst descendant wins using the imported severity order, DAG with two parents, isolated node. |
| Viewer | Manual: collapsed first paint, chevron-only expand, collapse forgets deep state, colour toggle, legend matches `statuses` order, one node with two inbound edges, source link opens a new tab. |

No browser automation in v1. Keep converter tests fast and dependency-free. Tests must use `--map` (or injected answers), never a live prompt.

## 12. Decisions

Resolved for v1:

1. **Orientation** — Left to right, each hierarchy level in a single column.
2. **Click target** — Chevron only. Node body, text, and source link do not expand or collapse.
3. **DAG rendering** — A node is drawn once. Multiple parents produce multiple inbound edges to that same node.
4. **How the viewer loads data** — `fetch('./graph.json')` from a static server. No embed-in-HTML path in v1.
5. **Which extra fields appear on a node** — The user chooses the data columns during CSV import. Those names are stored in `meta.displayFields`.
6. **Status catalogue** — There is no built-in list. At import the user defines the statuses, their display labels, colours, severity order, and fallback. That catalogue is written to `graph.json` as `statuses` and reused from the map file.

## 13. Future work

- Search, filter by status, and expand-to-node.
- Persist expand/colour state in `localStorage` or the URL.
- Additional adapters (Excel, outline markdown, Graphviz `dot`).
- Custom roll-up strategies and per-link types (dependency vs containment).
- Export the current view as SVG/PNG.
- In-browser load of a JSON file via file picker (no server).
- Editing an existing status catalogue without re-running the full column-mapping prompts.
