"""Design model: shape rules for columns, tables, relationships (no LLM involved)."""

import copy

import pytest
from pydantic import ValidationError

from dba_agent.model.schema import DesignModel, Relationship

PATIENT = {
    "name": "patient", "description": "A clinic patient",
    "columns": [
        {"name": "patient_id", "type": "integer", "nullable": False, "auto_increment": True},
        {"name": "full_name", "type": "string", "length": 120, "nullable": False},
        {"name": "national_id", "type": "string", "length": 10, "nullable": False, "unique": True},
    ],
    "primary_key": ["patient_id"],
}
APPOINTMENT = {
    "name": "appointment", "description": "A booked visit",
    "columns": [
        {"name": "appointment_id", "type": "integer", "nullable": False, "auto_increment": True},
        {"name": "patient_id", "type": "integer", "nullable": False},
        {"name": "status", "type": "string", "length": 20, "nullable": False, "default": "'booked'",
         "allowed_values": ["booked", "done", "cancelled"]},
        {"name": "fee", "type": "decimal", "precision": 10, "scale": 2},
    ],
    "primary_key": ["appointment_id"],
    "foreign_keys": [{"columns": ["patient_id"], "ref_table": "patient", "ref_columns": ["patient_id"]}],
    "indexes": [{"columns": ["patient_id"], "reason": "Patient history"}],
}
MODEL = {
    "tables": [PATIENT, APPOINTMENT],
    "relationships": [{"name": "books", "entity_a": "patient", "entity_b": "appointment",
                       "a_per_b": "exactly_one", "b_per_a": "zero_or_more",
                       "implemented_by": "appointment"}],
}


def with_change(path_fn):
    data = copy.deepcopy(MODEL)
    path_fn(data)
    return data


def test_valid_model():
    m = DesignModel.model_validate(MODEL)
    assert m.table("appointment").column("fee").scale == 2
    assert m.relationships[0].kind == "1:N"
    assert m.table("appointment").foreign_keys[0].on_delete == "RESTRICT"  # safe default


@pytest.mark.parametrize("change, message", [
    (lambda d: d["tables"][0]["columns"][1].pop("length"), "string needs `length`"),
    (lambda d: d["tables"][1]["columns"][3].pop("scale"), "decimal needs `precision` and `scale`"),
    (lambda d: d["tables"][0].update(name="Patient"), "must be snake_case"),
    (lambda d: d["tables"][0].update(primary_key=["id"]), "primary key uses unknown columns"),
    (lambda d: d["tables"][0]["columns"][0].update(nullable=True), "must be nullable=false"),
    (lambda d: d["tables"][0]["columns"].append(dict(d["tables"][0]["columns"][1])), "duplicate columns"),
    (lambda d: d["tables"][1]["foreign_keys"][0].update(columns=["patient_ref"]),
     "foreign key to 'patient' uses unknown columns"),
    (lambda d: d["tables"][1]["foreign_keys"][0].update(ref_columns=["a", "b"]), "column counts differ"),
    (lambda d: d["tables"][0]["columns"][1].update(auto_increment=True),
     "only allowed on integer types"),
    (lambda d: d["tables"].append(copy.deepcopy(PATIENT)), "Duplicate table names"),
])
def test_shape_rules(change, message):
    with pytest.raises(ValidationError, match=message):
        DesignModel.model_validate(with_change(change))


@pytest.mark.parametrize("a_per_b, b_per_a, kind", [
    ("exactly_one", "zero_or_more", "1:N"),
    ("zero_or_one", "exactly_one", "1:1"),
    ("one_or_more", "zero_or_more", "M:N"),
])
def test_relationship_kind(a_per_b, b_per_a, kind):
    r = Relationship(name="x", entity_a="a", entity_b="b", a_per_b=a_per_b, b_per_a=b_per_a,
                     implemented_by="b")
    assert r.kind == kind


def test_model_json_schema_is_generated():
    # This is what LLMService appends to the prompt; it must build without errors.
    schema = DesignModel.model_json_schema()
    assert "Table" in schema["$defs"] and "LogicalType" in schema["$defs"]
