"""The design model: one structured description of the whole database.

Every design document (ER diagram, logical schema, normalization notes) and schema.sql are
rendered from this object, so they can never disagree. The LLM creates and edits it; code
validates and renders it.

Two levels of rules:
- Here: rules about the *shape* of one table (types have their sizes, the primary key uses
  existing columns, names are valid identifiers…). Pydantic checks them on parsing.
- model/validate.py (next step): rules *across* tables (foreign keys point to real tables,
  many-to-many relationships have junction tables, every requirement is covered…).

Column types are LOGICAL (`string`, `decimal`, `datetime`…), not SQL types. The mapping to
VARCHAR / NVARCHAR / TEXT etc. depends on the DBMS and is done by code, which is why switching
the DBMS later only needs a re-render.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")  # snake_case; 63 chars = PostgreSQL's limit


def _check_identifier(name: str, what: str) -> str:
    if not IDENTIFIER.match(name):
        raise ValueError(f"{what} '{name}' must be snake_case: lowercase letters, digits and _, "
                         f"starting with a letter, at most 63 characters")
    return name


class LogicalType(str, Enum):
    INTEGER = "integer"
    BIGINT = "bigint"
    SMALLINT = "smallint"
    DECIMAL = "decimal"     # exact numbers, e.g. money: needs precision and scale
    BOOLEAN = "boolean"
    STRING = "string"       # short text with a maximum length: needs length
    TEXT = "text"           # long text without a practical limit
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"   # date + time
    UUID = "uuid"
    JSON = "json"
    BINARY = "binary"       # files, images


ReferentialAction = Literal["CASCADE", "RESTRICT", "SET NULL", "NO ACTION"]
TableKind = Literal["entity", "junction", "lookup"]
End = Literal["exactly_one", "zero_or_one", "one_or_more", "zero_or_more"]


class Column(BaseModel):
    name: str
    type: LogicalType
    length: int | None = Field(None, ge=1, description="Required for string")
    precision: int | None = Field(None, ge=1, le=38, description="Required for decimal: total digits")
    scale: int | None = Field(None, ge=0, description="Required for decimal: digits after the point")
    nullable: bool = True
    unique: bool = False
    auto_increment: bool = False
    default: str | None = Field(None, description="SQL literal or CURRENT_TIMESTAMP, e.g. '0', \"'pending'\"")
    allowed_values: list[str] = Field(default_factory=list,
                                      description="Fixed set of values (becomes a CHECK ... IN (...))")
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        return _check_identifier(v, "Column name")

    @model_validator(mode="after")
    def _type_details(self) -> "Column":
        if self.type == LogicalType.STRING and self.length is None:
            raise ValueError(f"Column '{self.name}': type string needs `length`")
        if self.type == LogicalType.DECIMAL:
            if self.precision is None or self.scale is None:
                raise ValueError(f"Column '{self.name}': type decimal needs `precision` and `scale`")
            if self.scale > self.precision:
                raise ValueError(f"Column '{self.name}': scale cannot exceed precision")
        if self.auto_increment and self.type not in (LogicalType.INTEGER, LogicalType.BIGINT,
                                                     LogicalType.SMALLINT):
            raise ValueError(f"Column '{self.name}': auto_increment is only allowed on integer types")
        return self


class ForeignKey(BaseModel):
    columns: list[str] = Field(min_length=1)
    ref_table: str
    ref_columns: list[str] = Field(min_length=1)
    on_delete: ReferentialAction = "RESTRICT"
    on_update: ReferentialAction = "NO ACTION"
    requirement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _same_length(self) -> "ForeignKey":
        if len(self.columns) != len(self.ref_columns):
            raise ValueError(f"Foreign key {self.columns} → {self.ref_table}{self.ref_columns}: "
                             "column counts differ")
        return self


class UniqueConstraint(BaseModel):
    columns: list[str] = Field(min_length=1)
    requirement_ids: list[str] = Field(default_factory=list)


class CheckConstraint(BaseModel):
    name: str
    expression: str = Field(description="Portable SQL boolean expression, e.g. 'end_time > start_time'")
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        return _check_identifier(v, "Check constraint name")


class Index(BaseModel):
    columns: list[str] = Field(min_length=1)
    unique: bool = False
    reason: str = Field("", description="Which query or report this index speeds up")


class Table(BaseModel):
    name: str
    kind: TableKind = "entity"
    description: str
    columns: list[Column] = Field(min_length=1)
    primary_key: list[str] = Field(min_length=1)
    foreign_keys: list[ForeignKey] = Field(default_factory=list)
    unique_constraints: list[UniqueConstraint] = Field(default_factory=list)
    checks: list[CheckConstraint] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        return _check_identifier(v, "Table name")

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)

    @model_validator(mode="after")
    def _local_consistency(self) -> "Table":
        names = [c.name for c in self.columns]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"Table '{self.name}': duplicate columns {dupes}")

        def unknown(cols: list[str], where: str) -> None:
            missing = [c for c in cols if c not in names]
            if missing:
                raise ValueError(f"Table '{self.name}': {where} uses unknown columns {missing}")

        unknown(self.primary_key, "primary key")
        for fk in self.foreign_keys:
            unknown(fk.columns, f"foreign key to '{fk.ref_table}'")
        for uc in self.unique_constraints:
            unknown(uc.columns, "unique constraint")
        for ix in self.indexes:
            unknown(ix.columns, "index")

        for col in self.primary_key:
            if self.column(col).nullable:
                raise ValueError(f"Table '{self.name}': primary key column '{col}' must be nullable=false")
        auto = [c.name for c in self.columns if c.auto_increment]
        if auto and (len(auto) > 1 or auto != self.primary_key):
            raise ValueError(f"Table '{self.name}': auto_increment is only allowed on a single-column "
                             f"primary key (found on {auto})")
        return self


class Relationship(BaseModel):
    """A conceptual relationship between two entities, as drawn on the ER diagram.

    Read it in both directions:
      each `entity_b` row relates to `a_per_b` of entity_a, and
      each `entity_a` row relates to `b_per_a` of entity_b.
    Example: patient – appointment: a_per_b = exactly_one (an appointment has one patient),
             b_per_a = zero_or_more (a patient has zero or more appointments).
    """

    name: str = Field(description="Verb phrase, e.g. 'books'")
    entity_a: str
    entity_b: str
    a_per_b: End
    b_per_a: End
    implemented_by: str = Field(description="Table holding the foreign key, or the junction table for M:N")
    requirement_ids: list[str] = Field(default_factory=list)

    @property
    def kind(self) -> Literal["1:1", "1:N", "M:N"]:
        many_a = self.a_per_b in ("one_or_more", "zero_or_more")
        many_b = self.b_per_a in ("one_or_more", "zero_or_more")
        if many_a and many_b:
            return "M:N"
        return "1:N" if (many_a or many_b) else "1:1"


class DesignModel(BaseModel):
    tables: list[Table] = Field(min_length=1)
    relationships: list[Relationship] = Field(default_factory=list)

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)

    @model_validator(mode="after")
    def _unique_table_names(self) -> "DesignModel":
        names = [t.name for t in self.tables]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"Duplicate table names: {dupes}")
        return self
