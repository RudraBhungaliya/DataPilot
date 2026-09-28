"""
Deterministic, request-adaptive Workflow Planner.

The plan is not a fixed template: the steps, their configuration and the
dependency chain are selected from the requirement (entity, requested fields,
filters, output format). Different prompts therefore produce different DAGs.
"""

import uuid
from typing import Any, Dict, List, Optional, Union

from app.ai.schemas import StructuredRequirement
from app.workflows.types import WorkflowStatus, StepStatus, StepType
from app.workflows.schemas import WorkflowDefinition, WorkflowStep
from app.workflows.validator import WorkflowValidator

# Fields that commonly require a second extraction pass (sparse on listing pages).
ENRICHABLE_FIELDS = {
    "founded_year", "employee_count", "headcount", "investors", "funding_date",
    "contact_email", "email", "phone", "valuation", "revenue", "founders",
    "address", "description",
}

# Entity-specific deduplication keys (fall back to requested fields).
ENTITY_DEDUPE_KEYS: Dict[str, List[str]] = {
    "job_posting": ["application_url", "company_name", "role"],
    "company": ["website", "company_name"],
    "startup": ["website", "company_name"],
    "repository": ["url", "name"],
    "article": ["url", "title"],
    "product": ["url", "name"],
}

_GENERIC_KEY_CANDIDATES = [
    "application_url", "url", "website", "company_name", "role", "title", "id", "name",
]


class WorkflowPlanner:
    """
    Builds a validated, request-adaptive execution workflow from a requirement.
    """

    def plan(
        self,
        requirement: Union[StructuredRequirement, Dict[str, Any]],
        workflow_id: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> WorkflowDefinition:
        req = (
            StructuredRequirement.model_validate(requirement)
            if isinstance(requirement, dict)
            else requirement
        )

        wid = workflow_id or str(uuid.uuid4())
        entity_name = req.entity.replace("_", " ").title()
        out_fmt = req.output_format.value if hasattr(req.output_format, "value") else str(req.output_format)
        required_fields = req.required_fields or []
        field_list = ", ".join(required_fields[:5]) if required_fields else "default attributes"

        steps: List[WorkflowStep] = []
        planning_notes: List[str] = []

        def add(step_type, name, description, depends_on, config):
            steps.append(
                WorkflowStep(
                    id=f"step_{len(steps) + 1}",
                    name=name,
                    type=step_type,
                    description=description,
                    order=len(steps) + 1,
                    depends_on=depends_on,
                    config=config,
                    status=StepStatus.PENDING,
                )
            )
            return steps[-1].id

        # 1. DISCOVER_SOURCES — always; fields inform ranking + availability
        discover = add(
            StepType.DISCOVER_SOURCES,
            "Discover Sources",
            f"Discover and rank high-confidence sources for {req.entity} that can provide {field_list}.",
            [],
            {
                "entity": req.entity,
                "required_fields": required_fields,
                "source_preferences": req.source_preferences,
                "location": req.location.model_dump() if req.location else None,
                "max_sources": 10,
            },
        )

        # 2. COLLECT_DATA
        collect = add(
            StepType.COLLECT_DATA,
            "Collect Data",
            "Gather raw documents from the discovered sources (rate-limited, policy-guarded).",
            [discover],
            {
                "entity": req.entity,
                "required_fields": required_fields,
                "time_constraint": req.time_constraint.model_dump() if req.time_constraint else None,
                "location": req.location.model_dump() if req.location else None,
            },
        )

        # 3. EXTRACT_DATA
        extract = add(
            StepType.EXTRACT_DATA,
            "Extract Data",
            f"Parse structured attributes ({field_list}) from the collected raw documents.",
            [collect],
            {"entity": req.entity, "required_fields": required_fields},
        )

        # 4. ENRICH_DATA — only when the request asks for sparse/enrichable fields
        last = extract
        enrichable = sorted(set(required_fields) & ENRICHABLE_FIELDS)
        if enrichable:
            last = add(
                StepType.ENRICH_DATA,
                "Enrich Data",
                f"Second extraction pass to fill sparse fields: {', '.join(enrichable)}.",
                [extract],
                {"required_fields": enrichable},
            )
            planning_notes.append(f"added ENRICH_DATA for sparse fields: {', '.join(enrichable)}")
        else:
            planning_notes.append("no enrichment step (no sparse/enrichable fields requested)")

        # 5. NORMALIZE_DATA
        normalize = add(
            StepType.NORMALIZE_DATA,
            "Normalize Data",
            "Cleanse text, coerce types and standardize date/location formats.",
            [last],
            {
                "standardize_dates": bool(req.time_constraint),
                "standardize_locations": bool(req.location),
                "target_fields": required_fields,
            },
        )

        # 6. VALIDATE_DATA
        validate = add(
            StepType.VALIDATE_DATA,
            "Validate Data",
            f"Verify records against {len(required_fields)} field constraints and {len(req.filters or [])} filter(s).",
            [normalize],
            {
                "required_fields": required_fields,
                "filters": [f.model_dump() for f in req.filters] if req.filters else [],
                "strict": False,
                "drop_invalid": True,
            },
        )

        # 7. DEDUPLICATE_DATA — keys depend on the entity and requested fields
        dedupe_keys = self._dedupe_keys(req.entity, required_fields)
        dedup = add(
            StepType.DEDUPLICATE_DATA,
            "Deduplicate Data",
            f"Remove records matching duplicate keys: {', '.join(dedupe_keys)}.",
            [validate],
            {"deduplication_keys": dedupe_keys, "match_threshold": 0.92},
        )
        planning_notes.append(f"dedup keys: {', '.join(dedupe_keys)}")

        # 8. BUILD_DATASET
        dataset = add(
            StepType.BUILD_DATASET,
            "Build Dataset",
            "Compile validated, deduplicated records into a structured dataset.",
            [dedup],
            {
                "entity": req.entity,
                "schema_fields": required_fields,
                "output_format": out_fmt,
            },
        )

        # 9. EXPORT_DATA — only for explicit file formats
        if out_fmt.lower() in ("csv", "json"):
            add(
                StepType.EXPORT_DATA,
                "Export Data",
                f"Export the compiled dataset as an optimized {out_fmt.upper()} artifact.",
                [dataset],
                {"format": out_fmt.lower(), "filename_prefix": f"{req.entity}_{out_fmt.lower()}"},
            )
            planning_notes.append(f"added EXPORT_DATA for {out_fmt.upper()} output")
        else:
            planning_notes.append("no export step (table output)")

        workflow = WorkflowDefinition(
            workflow_id=wid,
            name=f"{entity_name} Intelligence Collection",
            description=req.objective or f"Adaptive pipeline for {entity_name} entities.",
            status=WorkflowStatus.PLANNED,
            input_requirement=req,
            steps=steps,
            metadata={
                "generated_by": "adaptive_planner",
                "phase": "5+",
                "step_count": len(steps),
                "planning_notes": planning_notes,
                "original_prompt": prompt,
            },
        )

        WorkflowValidator.validate(workflow)
        return workflow

    @staticmethod
    def _dedupe_keys(entity: str, required_fields: List[str]) -> List[str]:
        entity_keys = ENTITY_DEDUPE_KEYS.get((entity or "").lower(), [])
        candidates = [k for k in entity_keys if k in (required_fields or [])]
        if not candidates:
            candidates = [k for k in _GENERIC_KEY_CANDIDATES if k in (required_fields or [])]
        if not candidates:
            candidates = (required_fields or [])[:2]
        if not candidates:
            candidates = ["id"]
        # keep order, dedupe
        seen = set()
        return [k for k in candidates if not (k in seen or seen.add(k))]
