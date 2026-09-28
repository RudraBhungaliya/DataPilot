"""
Background job handlers.

Each handler opens its own database session, so jobs run independently of any
HTTP request lifecycle.
"""

from typing import Any, Dict

from app.core.logger import logger


async def execute_workflow_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a planned workflow to completion."""
    workflow_id = payload.get("workflow_id")
    if not workflow_id:
        raise ValueError("workflow_id is required")

    from app.db.session import AsyncSessionLocal
    from app.services.workflow import WorkflowService

    async with AsyncSessionLocal() as db:
        service = WorkflowService()
        workflow = await service.execute_workflow(workflow_id=workflow_id, db=db)
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status.value,
            "error": workflow.error,
        }


async def execute_collection_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a collection job to completion."""
    collection_job_id = payload.get("collection_job_id")
    if not collection_job_id:
        raise ValueError("collection_job_id is required")

    from app.db.session import AsyncSessionLocal
    from app.collection.dependencies import get_collection_service

    async with AsyncSessionLocal() as db:
        service = get_collection_service()
        result = await service.execute_job(job_id=collection_job_id, db=db)
        return {
            "collection_job_id": collection_job_id,
            "status": result.status,
            "documents": len(result.documents),
        }
