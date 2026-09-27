"""
Collection Step Executor.
Integrates Phase 4 CollectionService into the Workflow Engine DAG.
"""

from typing import Optional, Dict, Any, List
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult
from app.workflows.schemas import WorkflowStep
from app.collection.service import CollectionService
from app.collection.schemas import CollectionRequest, CollectionLimits, SourceDefinition
from app.core.logger import logger


class CollectionStepExecutor(BaseStepExecutor):
    """
    Executes COLLECT_DATA workflow steps using real CollectionService.
    """

    def __init__(self, service: Optional[CollectionService] = None):
        self.service = service or CollectionService()

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

        try:
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

                # Run manager with selected sources
                result = await self.service.manager.execute_job(
                    request=col_req,
                    sources=selected,
                )
            else:
                # Run full job including discovery
                result = await self.service.execute_job(job_id=job.id)

            logger.info(
                f"CollectionStepExecutor finished: {len(result.documents)} documents collected "
                f"with status '{result.status}'"
            )

            is_success = result.status in ["COMPLETED", "PARTIAL_SUCCESS"]

            return StepResult(
                success=is_success,
                output=result.model_dump(mode="json"),
                error=result.errors[0]["error"] if not is_success and result.errors else None,
                metadata={
                    "is_mock": False,
                    "collector": "CollectionService",
                    "documents_collected": len(result.documents),
                    "failed_urls": result.metadata.failed_urls,
                    "zyte_used_count": result.metadata.zyte_used_count,
                    "status": result.status,
                },
            )

        except Exception as e:
            logger.error(f"CollectionStepExecutor failed: {e}", exc_info=True)
            return StepResult(
                success=False,
                error=f"Collection step execution failed: {str(e)}",
                metadata={"is_mock": False},
            )
