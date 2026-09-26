"""
Workflow Service.
Coordinates AI requirement parsing and workflow persistence.
"""

from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.ai.schemas import StructuredRequirement
from app.ai.parser import RequirementParser, RequirementParsingError
from app.models.workflow import Workflow
from app.core.logger import logger


class WorkflowService:
    """
    Business service layer managing workflow parsing, validation, and persistence.
    """

    def __init__(self, parser: Optional[RequirementParser] = None):
        self.parser = parser or RequirementParser()

    async def parse_requirement(
        self,
        prompt: str,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[StructuredRequirement, Optional[str]]:
        """
        Parses a natural language prompt into a StructuredRequirement and optionally saves a workflow record.

        :param prompt: User natural language prompt
        :param db: Optional database session
        :return: Tuple of (StructuredRequirement, workflow_id)
        """
        requirement = await self.parser.parse(prompt)

        workflow_id: Optional[str] = None
        if db is not None:
            try:
                status = "PARSED" if not requirement.is_ambiguous else "DRAFT"
                workflow = Workflow(
                    prompt=prompt,
                    parsed_requirement=requirement.model_dump(mode="json"),
                    status=status,
                )
                db.add(workflow)
                await db.commit()
                await db.refresh(workflow)
                workflow_id = workflow.id
                logger.info(f"Workflow record persisted: {workflow_id} (status: {status})")
            except Exception as e:
                logger.warning(f"Could not persist workflow record to DB (ignoring for resilience): {e}")
                await db.rollback()

        return requirement, workflow_id

    async def create_workflow(
        self,
        prompt: str,
        requirement: StructuredRequirement,
        db: AsyncSession,
        status: str = "PARSED",
    ) -> Workflow:
        """
        Explicitly saves or confirms a parsed workflow.
        """
        workflow = Workflow(
            prompt=prompt,
            parsed_requirement=requirement.model_dump(mode="json"),
            status=status,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        return workflow

    async def get_workflow_by_id(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> Optional[Workflow]:
        """Fetches a workflow by ID."""
        result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        return result.scalar_one_or_none()

    async def list_recent_workflows(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> List[Workflow]:
        """Lists recent workflows."""
        result = await db.execute(
            select(Workflow).order_by(desc(Workflow.created_at)).limit(limit)
        )
        return list(result.scalars().all())
