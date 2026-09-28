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


_IDENTITY_FIELD_CANDIDATES = (
    "company_name", "name", "title", "id", "url", "website", "repository",
    "product_name", "lab_name", "sponsor_name", "record_id",
)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _has_identity(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """A record is meaningful only if it carries at least one identifying value."""
    for field in list(required_fields or []) + list(_IDENTITY_FIELD_CANDIDATES):
        if _is_present((data or {}).get(field)):
            return True
    return any(_is_present(v) for v in (data or {}).values())


def validate_record(
    data: Dict[str, Any],
    required_fields: List[str],
    filters: Optional[List[Dict[str, Any]]] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates a single record.

    Lenient (default): a record is valid if it carries at least one identity value;
    missing requested fields are recorded (not fatal), filters whose field is absent
    are marked unverified, and completeness is scored.

    Strict: every requested field is required and every filter must be verifiable.
    """
    data = data or {}
    required_fields = required_fields or []
    present = [f for f in required_fields if _is_present(data.get(f))]
    missing = [f for f in required_fields if f not in present]
    completeness = round(len(present) / len(required_fields), 4) if required_fields else 1.0

    errors: List[str] = []
    warnings: List[str] = []

    if strict:
        for field in missing:
            errors.append(f"missing_required_field:{field}")

    if not _has_identity(data, required_fields):
        errors.append("no_identity_fields")

    for rule in filters or []:
        if not isinstance(rule, dict):
            continue
        field = rule.get("field")
        if field is not None and not _is_present(data.get(field)):
            # Filter cannot be evaluated because the field is missing
            if strict:
                errors.append(f"filter_failed:{field}")
            else:
                warnings.append(f"unverified_filter:{field}")
            continue
        if not _evaluate_filter(data, rule):
            errors.append(f"filter_failed:{field}")

    return {
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing,
        "completeness": completeness,
    }


def validate_records(
    records: List[ExtractionRecord],
    required_fields: List[str],
    filters: Optional[List[Dict[str, Any]]] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Validates records in place and returns aggregate statistics."""
    valid = 0
    invalid = 0
    missing_counts: Dict[str, int] = {}
    completeness_values: List[float] = []

    for record in records:
        result = validate_record(record.data, required_fields, filters, strict=strict)
        record.validation_errors = result["errors"] + result["warnings"]
        record.missing_fields = result["missing_fields"]
        record.completeness = result["completeness"]
        record.is_valid = len(result["errors"]) == 0

        completeness_values.append(result["completeness"])
        for field in result["missing_fields"]:
            missing_counts[field] = missing_counts.get(field, 0) + 1

        if record.is_valid:
            valid += 1
        else:
            invalid += 1

    mean_completeness = (
        round(sum(completeness_values) / len(completeness_values), 4) if completeness_values else 0.0
    )
    return {
        "valid": valid,
        "invalid": invalid,
        "mean_completeness": mean_completeness,
        "missing_counts": missing_counts,
    }


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


def records_to_jsonl(records: List[ExtractionRecord], fields: List[str]) -> str:
    """Newline-delimited JSON, one record per line (stream-friendly)."""
    lines = []
    for record in records:
        row = {field: record.data.get(field) for field in fields} if fields else record.data
        lines.append(json.dumps(row, default=str))
    return "\n".join(lines) + ("\n" if lines else "")
