"""Pydantic models for the shared graph JSON contract."""

from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

ColorMode = Literal["own", "rollup"]
SCHEMA_VERSION = "1.0"
NEUTRAL_STATUS_ID = "none"


class DataField(BaseModel):
    """A single extra field shown on a node body.

    Attributes:
        name: Display-field key, usually the CSV column header.
        value: Cell text for that column.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: str


class Status(BaseModel):
    """One entry in the user-defined status catalogue.

    Attributes:
        id: Stable key referenced by nodes. Usually the raw CSV value.
        label: Text shown on the chip and legend.
        color: CSS colour, preferably `#rrggbb`.
        severity: Higher means worse. Matches catalogue order, starting at 0.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    color: str
    severity: int = Field(ge=0)


class DocumentMeta(BaseModel):
    """Viewer header and display options.

    Attributes:
        title: Header title.
        description: Optional subtitle shown in the viewer header.
        default_color_mode: Initial own-status vs roll-up toggle.
        display_fields: Keys from each node's data to show on the body.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    title: str
    description: str = ""
    default_color_mode: ColorMode = Field(
        default="own",
        validation_alias=AliasChoices("defaultColorMode", "default_color_mode"),
        serialization_alias="defaultColorMode",
    )
    display_fields: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("displayFields", "display_fields"),
        serialization_alias="displayFields",
    )


class Node(BaseModel):
    """One item in the graph.

    Attributes:
        id: Unique expand key.
        title: Primary label.
        subtitle: Optional secondary line.
        status: Own status id from the catalogue.
        rollup_status: Worst-wins status over the subtree.
        source_url: Optional http(s) link to the source item.
        data: Extra fields selected at import.
        child_ids: Outgoing child ids, in link order.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    title: str
    subtitle: str | None = None
    status: str
    rollup_status: str = Field(
        validation_alias=AliasChoices("rollupStatus", "rollup_status"),
        serialization_alias="rollupStatus",
    )
    source_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceUrl", "source_url"),
        serialization_alias="sourceUrl",
    )
    data: list[DataField] = Field(default_factory=list)
    child_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("childIds", "child_ids"),
        serialization_alias="childIds",
    )

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_data(cls, value: object) -> list[DataField]:
        """Accept a JSON object or a list of `DataField` models."""
        if value is None:
            return []
        if isinstance(value, dict):
            fields: list[DataField] = []
            for key, raw in value.items():
                if not isinstance(key, str):
                    raise TypeError("data keys must be strings")
                fields.append(DataField(name=key, value=str(raw)))
            return fields
        if isinstance(value, list):
            return [item if isinstance(item, DataField) else DataField.model_validate(item) for item in value]
        raise TypeError("data must be an object or a list of fields")

    @field_serializer("data")
    def _serialize_data(self, fields: list[DataField]) -> dict[str, str]:
        """Write `data` as a JSON object for the viewer."""
        return {field.name: field.value for field in fields}


class Link(BaseModel):
    """A directed parent-to-child edge.

    Attributes:
        from_id: Parent node id.
        to_id: Child node id.
        label: Reserved; unused in v1 layout.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_id: str = Field(
        validation_alias=AliasChoices("from", "from_id"),
        serialization_alias="from",
    )
    to_id: str = Field(
        validation_alias=AliasChoices("to", "to_id"),
        serialization_alias="to",
    )
    label: str | None = None


class GraphDocument(BaseModel):
    """Canonical document consumed by the web viewer.

    Attributes:
        schema_version: Semver string. The viewer accepts `1.x`.
        meta: Title and display options.
        statuses: User-defined catalogue in severity order.
        nodes: Every item that can appear as a node.
        links: Directed parent-to-child edges.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        validation_alias=AliasChoices("schemaVersion", "schema_version"),
        serialization_alias="schemaVersion",
    )
    meta: DocumentMeta
    statuses: list[Status]
    nodes: list[Node]
    links: list[Link]


class RawRecord(BaseModel):
    """One CSV row after column mapping, before graph validation.

    Attributes:
        id: Item identity.
        title: Primary label.
        subtitle: Optional secondary line.
        status: Raw status cell, if a status column was mapped.
        parent_ids: Parent ids parsed from the links column.
        source_url: Raw URL cell, if mapped.
        data: Extra fields selected at import.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    subtitle: str | None = None
    status: str | None = None
    parent_ids: list[str] = Field(default_factory=list)
    source_url: str | None = None
    data: list[DataField] = Field(default_factory=list)


class ColumnMap(BaseModel):
    """Saved column roles and status catalogue from CSV import.

    Attributes:
        id: Header of the item id column.
        title: Header of the title column. May match `id`.
        status: Header of the status column, if any.
        links: Header of the parent-id column, if any.
        data: Headers of extra fields shown on each node.
        source_url: Header of the source URL column, if any.
        statuses: Catalogue written into `graph.json`.
        status_fallback: Catalogue id used for blank or unknown values.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    title: str
    status: str | None = None
    links: str | None = None
    data: list[str] = Field(default_factory=list)
    source_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceUrl", "source_url"),
        serialization_alias="sourceUrl",
    )
    statuses: list[Status] = Field(default_factory=list)
    status_fallback: str | None = Field(
        default=None,
        validation_alias=AliasChoices("statusFallback", "status_fallback"),
        serialization_alias="statusFallback",
    )


class TabularSource(BaseModel):
    """A headered table of string cells, independent of file format.

    Attributes:
        headers: Column names from the first row.
        rows: Data rows, each padded or trimmed to the header length.
    """

    model_config = ConfigDict(frozen=True)

    headers: list[str]
    rows: list[tuple[str, ...]]


def neutral_status() -> Status:
    """Return the single status used when no status column is mapped."""
    return Status(id=NEUTRAL_STATUS_ID, label="None", color="#757575", severity=0)


def with_ordered_severity(statuses: list[Status]) -> list[Status]:
    """Return copies of `statuses` with severity set from list order.

    Args:
        statuses: Catalogue in least-severe to most-severe order.

    Returns:
        New status models whose `severity` matches their index.
    """
    return [
        Status(id=item.id, label=item.label, color=item.color, severity=index)
        for index, item in enumerate(statuses)
    ]
