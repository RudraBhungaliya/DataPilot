"""
Deterministic Workflow Planner.
Converts structured requirements into valid, executable DAG workflow plans.
"""

import uuid
from typing import Dict, Any, Union, Optional, List
from app.ai.schemas import StructuredRequirement, OutputFormat
from app.workflows.types import WorkflowStatus, StepStatus, StepType
from app.workflows.schemas import WorkflowDefinition, WorkflowStep
from app.workflows.validator import WorkflowValidator


class WorkflowPlanner:
    """
    Deterministic planning engine that translates business data requirements
    into validated, structured execution workflows without requiring LLM inference.
    """

    def plan(
        self,
        requirement: Union[StructuredRequirement, Dict[str, Any]],
        workflow_id: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> WorkflowDefinition:
        """
        Generates a validated WorkflowDefinition from a StructuredRequirement.

        :param requirement: StructuredRequirement object or dictionary
        :param workflow_id: Optional ID to preserve or generate new
        :param prompt: Optional original natural language prompt
        :return: Validated WorkflowDefinition
        """
        # Normalize requirement to StructuredRequirement instance
        if isinstance(requirement, dict):
            req = StructuredRequirement.model_validate(requirement)
        else:
            req = requirement

        wid = workflow_id or str(uuid.uuid4())
        steps: List[WorkflowStep] = []
        step_counter = 1

        # Determine readable workflow name and description
        entity_name = req.entity.replace("_", " ").title()
        workflow_name = f"{entity_name} Intelligence Collection"
        workflow_desc = (
            req.objective
            or f"Autonomous collection, extraction, and validation pipeline for {entity_name} entities."
        )

        # Step 1: DISCOVER_SOURCES
        discover_id = f"step_{step_counter}"
        step_counter += 1
        steps.append(
            WorkflowStep(
                id=discover_id,
                name="Discover Sources",
                type=StepType.DISCOVER_SOURCES,
                description=f"Identify and rank high-confidence sources and platforms for {req.entity} entities.",
                order=len(steps) + 1,
                depends_on=[],
                config={
                    "entity": req.entity,
                    "source_preferences": req.source_preferences,
                    "location": req.location.model_dump() if req.location else None,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 2: COLLECT_DATA
        collect_id = f"step_{step_counter}"
        step_counter += 1
        steps.append(
            WorkflowStep(
                id=collect_id,
                name="Collect Data",
                type=StepType.COLLECT_DATA,
                description=f"Gather raw records and content payloads from discovered sources.",
                order=len(steps) + 1,
                depends_on=[discover_id],
                config={
                    "entity": req.entity,
                    "time_constraint": req.time_constraint.model_dump() if req.time_constraint else None,
                    "location": req.location.model_dump() if req.location else None,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 3: EXTRACT_DATA
        extract_id = f"step_{step_counter}"
        step_counter += 1
        fields_preview = ", ".join(req.required_fields[:4]) if req.required_fields else "default attributes"
        steps.append(
            WorkflowStep(
                id=extract_id,
                name="Extract Data",
                type=StepType.EXTRACT_DATA,
                description=f"Parse structured attributes ({fields_preview}) from collected raw payloads.",
                order=len(steps) + 1,
                depends_on=[collect_id],
                config={
                    "entity": req.entity,
                    "required_fields": req.required_fields,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 4: NORMALIZE_DATA
        normalize_id = f"step_{step_counter}"
        step_counter += 1
        steps.append(
            WorkflowStep(
                id=normalize_id,
                name="Normalize Data",
                type=StepType.NORMALIZE_DATA,
                description="Cleanse text, coerce schema types, and standardize date and location formats.",
                order=len(steps) + 1,
                depends_on=[extract_id],
                config={
                    "standardize_dates": bool(req.time_constraint),
                    "standardize_locations": bool(req.location),
                    "target_fields": req.required_fields,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 5: VALIDATE_DATA (included for structured workflows with filters or field constraints)
        validate_id = f"step_{step_counter}"
        step_counter += 1
        filter_count = len(req.filters) if req.filters else 0
        steps.append(
            WorkflowStep(
                id=validate_id,
                name="Validate Data",
                type=StepType.VALIDATE_DATA,
                description=f"Verify records against schema constraints and {filter_count} filter conditions.",
                order=len(steps) + 1,
                depends_on=[normalize_id],
                config={
                    "filters": [f.model_dump() for f in req.filters] if req.filters else [],
                    "required_fields": req.required_fields,
                    "drop_invalid": True,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 6: DEDUPLICATE_DATA
        dedup_id = f"step_{step_counter}"
        step_counter += 1
        # Pick candidate deduplication keys based on required_fields
        candidate_keys = ["application_url", "url", "website", "company_name", "role", "title", "id", "name"]
        dedupe_keys = [k for k in candidate_keys if k in req.required_fields]
        if not dedupe_keys:
            dedupe_keys = req.required_fields[:2] if req.required_fields else ["id"]

        steps.append(
            WorkflowStep(
                id=dedup_id,
                name="Deduplicate Data",
                type=StepType.DEDUPLICATE_DATA,
                description=f"Remove redundant records matching duplicate keys: {', '.join(dedupe_keys)}.",
                order=len(steps) + 1,
                depends_on=[validate_id],
                config={
                    "deduplication_keys": dedupe_keys,
                    "match_threshold": 0.95,
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 7: BUILD_DATASET
        dataset_id = f"step_{step_counter}"
        step_counter += 1
        steps.append(
            WorkflowStep(
                id=dataset_id,
                name="Build Dataset",
                type=StepType.BUILD_DATASET,
                description=f"Compile validated and deduplicated records into a structured dataset.",
                order=len(steps) + 1,
                depends_on=[dedup_id],
                config={
                    "entity": req.entity,
                    "schema_fields": req.required_fields,
                    "output_format": req.output_format.value if hasattr(req.output_format, "value") else str(req.output_format),
                },
                status=StepStatus.PENDING,
            )
        )

        # Step 8 (Conditional): EXPORT_DATA
        # Only added when the user explicitly requests an export format like CSV or JSON file
        out_fmt = req.output_format.value if hasattr(req.output_format, "value") else str(req.output_format)
        if out_fmt.lower() in ["csv", "json"]:
            export_id = f"step_{step_counter}"
            step_counter += 1
            steps.append(
                WorkflowStep(
                    id=export_id,
                    name="Export Data",
                    type=StepType.EXPORT_DATA,
                    description=f"Export the compiled dataset as an optimized {out_fmt.upper()} artifact.",
                    order=len(steps) + 1,
                    depends_on=[dataset_id],
                    config={
                        "format": out_fmt.lower(),
                        "filename_prefix": f"{req.entity}_{out_fmt.lower()}",
                    },
                    status=StepStatus.PENDING,
                )
            )

        workflow = WorkflowDefinition(
            workflow_id=wid,
            name=workflow_name,
            description=workflow_desc,
            status=WorkflowStatus.PLANNED,
            input_requirement=req,
            steps=steps,
            metadata={
                "generated_by": "deterministic_planner",
                "phase": 3,
                "step_count": len(steps),
                "original_prompt": prompt,
            },
        )

        # Ensure definition passes structural and dependency validation
        WorkflowValidator.validate(workflow)

        return workflow
