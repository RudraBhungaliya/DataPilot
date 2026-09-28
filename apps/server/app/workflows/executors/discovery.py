"""
Source Discovery Step Executor.
Integrates Phase 4 SourceDiscovery into the Workflow Engine DAG.
"""

from typing import Optional, Dict, Any, List
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult
from app.workflows.schemas import WorkflowStep
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.dependencies import get_source_registry
from app.collection.schemas import CollectionRequest, CollectionLimits, CollectionStrategy
from app.core.logger import logger


class SourceDiscoveryStepExecutor(BaseStepExecutor):
    """
    Executes DISCOVER_SOURCES workflow steps using real SourceDiscovery.
    """

    def __init__(self, discovery: Optional[SourceDiscovery] = None):
        self.discovery = discovery or SourceDiscovery(registry=get_source_registry())

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        entity = req.entity if hasattr(req, "entity") else (req.get("entity") if isinstance(req, dict) else "item")
        objective = req.objective if hasattr(req, "objective") else (req.get("objective") if isinstance(req, dict) else f"Collect {entity} data")
        req_fields = req.required_fields if hasattr(req, "required_fields") else (req.get("required_fields", []) if isinstance(req, dict) else [])
        source_prefs = req.source_preferences if hasattr(req, "source_preferences") else (req.get("source_preferences", []) if isinstance(req, dict) else [])

        # Extract constraints
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
            limits=CollectionLimits(max_sources=step.config.get("max_sources", 10)),
        )

        try:
            sources = await self.discovery.discover_sources(col_req)
            logger.info(f"SourceDiscoveryStepExecutor found {len(sources)} sources for workflow {context.workflow_id}")

            return StepResult(
                success=True,
                output={
                    "sources_discovered": len(sources),
                    "sources": [s.model_dump(mode="json") for s in sources],
                    "entity": entity,
                    "is_mock": False,
                },
                metadata={
                    "is_mock": False,
                    "provider": "SourceDiscovery",
                    "sources_count": len(sources),
                },
            )
        except Exception as e:
            logger.error(f"SourceDiscoveryStepExecutor failed: {e}", exc_info=True)
            return StepResult(
                success=False,
                error=f"Source discovery failed: {str(e)}",
                metadata={"is_mock": False},
            )
