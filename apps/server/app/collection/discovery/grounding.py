"""
Field-availability grounding.

Before collection, estimates whether the requested fields are actually
obtainable from the discovered sources, so the platform can warn the user,
broaden sources, or plan enrichment instead of silently returning empty columns.
"""

from typing import List

from app.collection.schemas import SourceDefinition


def _field_tokens(field: str) -> List[str]:
    return [t for t in field.lower().replace("-", "_").split("_") if len(t) > 2]


def _source_supports(source: SourceDefinition, field: str) -> bool:
    tokens = _field_tokens(field)
    if not tokens:
        return False
    haystack = " ".join(
        [c.lower() for c in (source.capabilities or [])]
        + [source.name.lower(), (source.domain or "").lower()]
    )
    return any(token in haystack for token in tokens)


def estimate_field_availability(
    required_fields: List[str],
    sources: List[SourceDefinition],
) -> List[dict]:
    """
    Returns a per-field availability estimate based on declared source
    capabilities. This is deterministic and network-free; it is a signal, not a
    guarantee (a live probe can refine it).
    """
    availability: List[dict] = []
    for field in required_fields or []:
        providers = [s.source_id for s in sources if _source_supports(s, field)]
        if providers:
            status, reason = "obtainable", f"{len(providers)} source(s) declare this capability"
        else:
            status, reason = "unknown", "no discovered source declares this capability"
        availability.append(
            {
                "field": field,
                "status": status,
                "reason": reason,
                "sources": providers,
            }
        )
    return availability


def availability_score(required_fields: List[str], sources: List[SourceDefinition]) -> float:
    """Fraction of requested fields that at least one source can likely provide."""
    if not required_fields:
        return 1.0
    estimates = estimate_field_availability(required_fields, sources)
    obtainable = sum(1 for e in estimates if e["status"] == "obtainable")
    return round(obtainable / len(required_fields), 3)
