"""
Phase 5 pipeline stage helpers: normalization, validation, deduplication, export.

All functions are deterministic and side-effect free, operating on
ExtractionRecord instances.
"""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.pipeline.schemas import ExtractionRecord


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes keys to snake_case and collapses whitespace in string values."""
    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        clean_key = _normalize_key(key)
        if clean_key.startswith("_"):  # drop model hints like _confidence
            continue
        if isinstance(value, str):
            normalized[clean_key] = " ".join(value.strip().split())
        else:
            normalized[clean_key] = value
    return normalized


def normalize_records(records: List[ExtractionRecord]) -> int:
    """Normalizes records in place. Returns the number processed."""
    for record in records:
        record.data = normalize_data(record.data)
    return len(records)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_OPERATORS = {
    "equals", "not_equals", "greater_than", "less_than",
    "greater_than_or_equal", "less_than_or_equal",
    "contains", "not_contains", "in_list", "not_in_list", "between",
}


def _coerce_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _evaluate_filter(data: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """Returns True when the record SATISFIES the filter rule."""
    field = rule.get("field")
    operator = str(rule.get("operator", "equals")).lower().replace(" ", "_")
    expected = rule.get("value")
    if field is None:
        return True
    actual = data.get(field)

    if operator in ("greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "between"):
        actual_num = _coerce_number(actual)
        if actual_num is None:
            return False
        if operator == "greater_than":
            return actual_num > float(expected)
        if operator == "less_than":
            return actual_num < float(expected)
        if operator == "greater_than_or_equal":
            return actual_num >= float(expected)
        if operator == "less_than_or_equal":
            return actual_num <= float(expected)
        # between -> expected must be a 2-item list
        if isinstance(expected, (list, tuple)) and len(expected) == 2:
            return float(expected[0]) <= actual_num <= float(expected[1])
        return False

    if operator == "contains":
        return expected is not None and str(expected).lower() in str(actual or "").lower()
    if operator == "not_contains":
        return expected is not None and str(expected).lower() not in str(actual or "").lower()
    if operator == "in_list":
        return isinstance(expected, list) and actual in expected
    if operator == "not_in_list":
        return isinstance(expected, list) and actual not in expected
    if operator == "not_equals":
        return actual != expected
    return actual == expected


def validate_record(
    data: Dict[str, Any],
    required_fields: List[str],
    filters: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """Returns a list of validation error strings (empty list means valid)."""
    errors: List[str] = []
    for field in required_fields or []:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"missing_required_field:{field}")

    for rule in filters or []:
        if not isinstance(rule, dict):
            continue
        if not _evaluate_filter(data, rule):
            errors.append(f"filter_failed:{rule.get('field')}")

    return errors


def validate_records(
    records: List[ExtractionRecord],
    required_fields: List[str],
    filters: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, int]:
    """Validates records in place. Returns {'valid': n, 'invalid': m}."""
    valid = 0
    invalid = 0
    for record in records:
        errors = validate_record(record.data, required_fields, filters)
        record.validation_errors = errors
        record.is_valid = len(errors) == 0
        if record.is_valid:
            valid += 1
        else:
            invalid += 1
    return {"valid": valid, "invalid": invalid}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def build_dedupe_key(data: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Builds a normalized composite key from the requested dedupe keys."""
    if not keys:
        return None
    parts = []
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        parts.append(str(value).strip().lower())
    if not parts:
        return None
    return "|".join(parts)


def mark_duplicates(
    records: List[ExtractionRecord],
    keys: List[str],
    match_threshold: float = 0.95,
) -> int:
    """
    Marks duplicate records in place (keeping the first occurrence of each key).
    Returns the number of records marked as duplicates.
    """
    seen: Dict[str, str] = {}
    duplicates = 0
    for record in records:
        key = build_dedupe_key(record.data, keys)
        record.dedupe_key = key
        if not key:
            record.is_duplicate = False
            continue
        if key in seen:
            record.is_duplicate = True
            duplicates += 1
        else:
            seen[key] = record.record_id
            record.is_duplicate = False
    return duplicates


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def records_to_csv(records: List[ExtractionRecord], fields: List[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({field: record.data.get(field) for field in fields})
    return buffer.getvalue()


def records_to_json(records: List[ExtractionRecord], fields: List[str]) -> str:
    rows = []
    for record in records:
        if fields:
            rows.append({field: record.data.get(field) for field in fields})
        else:
            rows.append(record.data)
    return json.dumps(rows, indent=2, default=str)
