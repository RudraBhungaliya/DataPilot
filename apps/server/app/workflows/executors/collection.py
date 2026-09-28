"""
Collection Step Executor.
Integrates Phase 4 CollectionService into the Workflow Engine DAG.
"""

from typing import Optional, Dict, Any, List
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult
from app.workflows.schemas import WorkflowStep
from app.collection.service import CollectionService
from app.collection.dependencies import get_collection_service
from app.collection.schemas import (
    CollectionRequest,
    CollectionResult,
    CollectionLimits,
    SourceDefinition,
    JobStatus,
)
from app.core.logger import logger


class CollectionStepExecutor(BaseStepExecutor):
    """
    Executes COLLECT_DATA workflow steps using the real CollectionService.
    """

    def __init__(self, service: Optional[CollectionService] = None):
        self.service = service or get_collection_service()

    @staticmethod
    def _to_step_result(result: CollectionResult, job_id: str) -> StepResult:
        """Maps a CollectionResult onto a workflow StepResult."""
        is_success = result.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL_SUCCESS.value)
        is_human_action = result.status == JobStatus.HUMAN_ACTION_REQUIRED.value

        return StepResult(
            success=is_success,
            output=result.model_dump(mode="json"),
            error=(
                "Human action required: CAPTCHA encountered on source. Please complete verification and resume."
                if is_human_action
                else (result.errors[0]["error"] if not is_success and result.errors else None)
            ),
            metadata={
                "is_mock": False,
                "collector": "CollectionService",
                "job_id": job_id,
                "documents_collected": len(result.documents),
                "failed_urls": result.metadata.failed_urls,
                "zyte_used_count": result.metadata.zyte_used_count,
                "status": result.status,
                "human_action_required": is_human_action,
                "checkpoint": result.checkpoint if is_human_action else None,
            },
        )

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        entity = req.entity if hasattr(req, "entity") else (req.get("entity") if isinstance(req, dict) else "item")
        objective = req.objective if hasattr(req, "objective") else (req.get("objective") if isinstance(req, dict) else f"Collect {entity} data")
        req_fields = req.required_fields if hasattr(req, "required_fields") else (req.get("required_fields", []) if isinstance(req, dict) else [])
        source_prefs = req.source_preferences if hasattr(req, "source_preferences") else (req.get("source_preferences", []) if isinstance(req, dict) else [])

        constraints: Dict[str, Any] = {}
        if hasattr(req, "location") and req.location:
            constraints["location"] = req.location.model_dump() if hasattr(req.location, "model_dump") else req.location
        if hasattr(req, "time_constraint") and req.time_constraint:
            constraints["time_constraint"] = req.time_constraint.model_dump() if hasattr(req.time_constraint, "model_dump") else req.time_constraint

        try:
            # Resume path: if this step previously paused for human action, resume the
            # existing collection job instead of starting a new one (which would duplicate data).
            existing_job_id = step.metadata.get("job_id")
            if existing_job_id and step.metadata.get("human_action_required"):
                try:
                    existing_job = await self.service.get_job(existing_job_id)
                    if existing_job is not None and existing_job.status == JobStatus.HUMAN_ACTION_REQUIRED.value:
                        logger.info(
                            f"Resuming paused collection job '{existing_job_id}' for step '{step.id}'"
                        )
                        result = await self.service.resume_job(job_id=existing_job_id)
                        step.metadata["human_action_required"] = False
                        return self._to_step_result(result, existing_job_id)
                    # Not resumable -> fall through and start a fresh job
                    step.metadata["human_action_required"] = False
                except Exception as resume_err:
                    logger.warning(
                        f"Could not resume collection job '{existing_job_id}', starting fresh: {resume_err}"
                    )
                    step.metadata["human_action_required"] = False

            col_req = CollectionRequest(
                workflow_id=context.workflow_id,
                objective=objective,
                entity=entity,
                required_fields=req_fields,
                constraints=constraints,
                source_preferences=source_prefs,
                limits=CollectionLimits(
                    max_sources=step.config.get("max_sources", 5),
                    max_documents=step.config.get("max_documents", 50),
                ),
            )

            # 1. Create collection job
            job = await self.service.create_job(col_req)

            # 2. Check if upstream DISCOVER_SOURCES passed discovered sources
            upstream_sources: List[SourceDefinition] = []
            for dep_id in step.depends_on:
                dep_output = context.get_step_output(dep_id)
                if isinstance(dep_output, dict) and "sources" in dep_output:
                    for s_dict in dep_output["sources"]:
                        try:
                            upstream_sources.append(SourceDefinition.model_validate(s_dict))
                        except Exception:
                            pass

            if upstream_sources:
                job.discovered_sources = [s.model_dump(mode="json") for s in upstream_sources]
                selected = self.service.select_sources(upstream_sources, col_req)
                job.selected_sources = [s.model_dump(mode="json") for s in selected]

                result = await self.service.manager.execute_job(
                    request=col_req,
                    sources=selected,
                    job_id=job.id,
                )
            else:
                # Run full job including discovery
                result = await self.service.execute_job(job_id=job.id)

            logger.info(
                f"CollectionStepExecutor finished: {len(result.documents)} documents collected "
                f"with status '{result.status}'"
            )
            return self._to_step_result(result, job.id)

        except Exception as e:
            logger.error(f"CollectionStepExecutor failed: {e}", exc_info=True)
            return StepResult(
                success=False,
                error=f"Collection step execution failed: {str(e)}",
                metadata={"is_mock": False},
            )
