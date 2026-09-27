"""
Workflow Service.
Coordinates AI requirement parsing, workflow planning, DAG execution, and persistence.
"""

from typing import Optional, Tuple, List, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.ai.schemas import StructuredRequirement
from app.ai.parser import RequirementParser, RequirementParsingError
from app.models.workflow import Workflow
from app.workflows.types import WorkflowStatus, StepStatus
from app.workflows.schemas import WorkflowDefinition, WorkflowStep
from app.workflows.planner import WorkflowPlanner
from app.workflows.engine import WorkflowEngine
from app.workflows.registry import ExecutorRegistry, get_default_registry
from app.core.logger import logger


class WorkflowService:
    """
    Business service layer managing workflow parsing, planning, validation, execution, and persistence.
    """

    def __init__(
        self,
        parser: Optional[RequirementParser] = None,
        planner: Optional[WorkflowPlanner] = None,
        engine: Optional[WorkflowEngine] = None,
    ):
        self.parser = parser or RequirementParser()
        self.planner = planner or WorkflowPlanner()
        self.engine = engine or WorkflowEngine(get_default_registry())

    async def parse_requirement(
        self,
        prompt: str,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[StructuredRequirement, Optional[str]]:
        """
        Parses a natural language prompt into a StructuredRequirement and optionally saves a workflow record.
        """
        requirement = await self.parser.parse(prompt)

        workflow_id: Optional[str] = None
        if db is not None:
            try:
                status = WorkflowStatus.PARSED.value if not requirement.is_ambiguous else WorkflowStatus.DRAFT.value
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

    async def plan_workflow(
        self,
        requirement: Union[StructuredRequirement, Dict[str, Any]],
        prompt: Optional[str] = None,
        workflow_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> WorkflowDefinition:
        """
        Generates a validated WorkflowDefinition from a StructuredRequirement and persists it.
        """
        workflow_def = self.planner.plan(
            requirement=requirement,
            workflow_id=workflow_id,
            prompt=prompt,
        )

        if db is not None:
            try:
                # Check if existing workflow record exists
                target_id = workflow_def.workflow_id
                existing = await self.get_workflow_by_id(target_id, db=db)

                if existing:
                    existing.workflow_definition = workflow_def.model_dump(mode="json")
                    existing.status = WorkflowStatus.PLANNED.value
                    if prompt:
                        existing.prompt = prompt
                    if isinstance(requirement, StructuredRequirement):
                        existing.parsed_requirement = requirement.model_dump(mode="json")
                    elif isinstance(requirement, dict):
                        existing.parsed_requirement = requirement
                    await db.commit()
                    await db.refresh(existing)
                    logger.info(f"Updated existing workflow record {target_id} with planned workflow definition.")
                else:
                    new_record = Workflow(
                        id=target_id,
                        prompt=prompt or workflow_def.description,
                        parsed_requirement=(
                            requirement.model_dump(mode="json")
                            if isinstance(requirement, StructuredRequirement)
                            else requirement
                        ),
                        workflow_definition=workflow_def.model_dump(mode="json"),
                        status=WorkflowStatus.PLANNED.value,
                    )
                    db.add(new_record)
                    await db.commit()
                    await db.refresh(new_record)
                    logger.info(f"Created new workflow record {target_id} with planned definition.")
            except Exception as e:
                logger.warning(f"Could not persist planned workflow definition to DB: {e}")
                await db.rollback()

        return workflow_def

    async def execute_workflow(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> WorkflowDefinition:
        """
        Executes a workflow definition by ID using step executors.
        Persists progress and step results into the database.
        """
        record = await self.get_workflow_by_id(workflow_id=workflow_id, db=db)
        if not record:
            raise ValueError(f"Workflow with ID '{workflow_id}' not found.")

        # Reconstruct WorkflowDefinition
        if record.workflow_definition:
            workflow_def = WorkflowDefinition.model_validate(record.workflow_definition)
        elif record.parsed_requirement:
            # Auto-plan if not previously planned
            workflow_def = self.planner.plan(
                requirement=record.parsed_requirement,
                workflow_id=workflow_id,
                prompt=record.prompt,
            )
        else:
            raise ValueError(f"Workflow '{workflow_id}' does not have a requirement or workflow definition.")

        # Callback to save intermediate step changes to database
        async def on_step_update(wf: WorkflowDefinition, step: WorkflowStep) -> None:
            try:
                record.status = wf.status.value
                record.workflow_definition = wf.model_dump(mode="json")
                if wf.error:
                    record.error = wf.error
                await db.commit()
            except Exception as persist_err:
                logger.warning(f"Failed to persist intermediate step update for {step.id}: {persist_err}")
                await db.rollback()

        # Execute using WorkflowEngine
        executed_def = await self.engine.execute(
            workflow=workflow_def,
            on_step_update=on_step_update,
        )

        # Final persistence
        try:
            record.status = executed_def.status.value
            record.workflow_definition = executed_def.model_dump(mode="json")
            record.error = executed_def.error
            record.execution_metadata = executed_def.metadata
            await db.commit()
            await db.refresh(record)
            logger.info(f"Workflow '{workflow_id}' execution saved with status {record.status}.")
        except Exception as e:
            logger.error(f"Failed to save completed workflow state for '{workflow_id}': {e}")
            await db.rollback()

        return executed_def

    async def get_workflow(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> Optional[Workflow]:
        """Alias for get_workflow_by_id."""
        return await self.get_workflow_by_id(workflow_id=workflow_id, db=db)

    async def get_workflow_by_id(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> Optional[Workflow]:
        """Fetches a workflow database model by ID."""
        result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        return result.scalar_one_or_none()

    async def get_workflow_definition(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> Optional[WorkflowDefinition]:
        """Retrieves and deserializes the full WorkflowDefinition for a given workflow ID."""
        record = await self.get_workflow_by_id(workflow_id=workflow_id, db=db)
        if not record or not record.workflow_definition:
            return None
        return WorkflowDefinition.model_validate(record.workflow_definition)

    async def get_workflow_steps(
        self,
        workflow_id: str,
        db: AsyncSession,
    ) -> Optional[List[WorkflowStep]]:
        """Retrieves the list of steps for a given workflow."""
        workflow_def = await self.get_workflow_definition(workflow_id=workflow_id, db=db)
        if not workflow_def:
            return None
        return workflow_def.steps

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
