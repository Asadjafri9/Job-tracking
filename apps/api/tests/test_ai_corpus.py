"""AI-004 quality corpus: schema + source-reference rules for provider outputs.

Every case file under tests/corpus exercises the typed contract from both
sides: the recorded input must validate against the operation's input model,
then one output must pass the output schema and source-reference rules, and
poisoned outputs must fail schema validation or the reference rules. These
are offline contract checks - no provider traffic, no live-model claims.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.contract import (
    OPERATION_INPUTS,
    validate_input,
    validate_output,
)

CORPUS_DIR = Path(__file__).parent / "corpus"


def _reference_violation(kind: str, payload: dict[str, Any], output: dict[str, Any]) -> str | None:
    if kind == "EXTRACTION":
        section_ids = {section["section_id"] for section in payload["sections"]}
        for candidate in output["candidates"]:
            if candidate["section_id"] not in section_ids:
                return f"section_id {candidate['section_id']} absent from input"
        return None
    if kind == "AUTOFILL":
        fields = {question["field_id"]: question for question in payload["questions"]}
        fact_keys = {fact["fact_key"] for fact in payload["facts"]}
        for answer in output["answers"]:
            if answer["field_id"] not in fields:
                return f"field_id {answer['field_id']} absent from input"
            if not set(answer.get("used_fact_keys") or []) <= fact_keys:
                return "used_fact_keys cite unprovided facts"
            if not set(answer.get("option_ids") or []) <= set(
                fields[answer["field_id"]].get("options") or []
            ):
                return "option_ids cite unprovided options"
        return None
    if kind == "CLASSIFY":
        native_ids = {posting["native_id"] for posting in payload["postings"]}
        for verdict in output["results"]:
            if verdict["native_id"] not in native_ids:
                return f"native_id {verdict['native_id']} absent from input"
        return None
    return None


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(CORPUS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        for case in data["cases"]:
            case["_kind"] = data["kind"]
            case["_file"] = path.name
            cases.append(case)
    return cases


@pytest.mark.parametrize("case", _cases(), ids=lambda c: f"{c['_file']}::{c['name']}")
def test_corpus_case(case: dict[str, Any]) -> None:
    kind = case["_kind"]
    assert kind in OPERATION_INPUTS, f"unknown operation kind {kind}"
    payload = validate_input(kind, case["input"])
    payload_dict = payload.model_dump()

    if "expect_valid" in case:
        output = validate_output(kind, case["expect_valid"])
        violation = _reference_violation(kind, payload_dict, output.model_dump())
        assert violation is None, f"valid case broke a reference rule: {violation}"
        return

    if "expect_schema_violation" in case:
        with pytest.raises((ValidationError, ValueError)):
            validate_output(kind, case["expect_schema_violation"])
        return

    if "expect_reference_violation" in case:
        output = validate_output(kind, case["expect_reference_violation"])
        violation = _reference_violation(kind, payload_dict, output.model_dump())
        assert violation is not None, "poisoned output was not caught by reference rules"
        return

    pytest.fail(f"case {case['name']} has no expectation")


def test_every_operation_kind_has_a_corpus_file() -> None:
    kinds_on_disk = {json.loads(path.read_text())["kind"] for path in CORPUS_DIR.glob("*.json")}
    assert set(OPERATION_INPUTS) <= kinds_on_disk
