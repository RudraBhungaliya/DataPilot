"""
Workflows and AI Requirement Parsing Endpoints.
Provides Phase 2 requirement parsing and Phase 3 workflow planning and execution APIs.
"""

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import (
    RequirementParseRequest,
    RequirementParseResponse,
    StructuredRequirement,
)
from app.ai.parser import RequirementParsingError
from app.ai.provider import LLMAuthenticationError, LLMTimeoutError
from app.workflows.schemas import (
    WorkflowDefinition,
    PlanWorkflowRequest,
    PlanWorkflowResponse,
    ExecuteWorkflowResponse,
    WorkflowStepsResponse,
)
from app.workflows.validator import WorkflowValidationError
from app.services.workflow import WorkflowService, WorkflowStateError
from app.db.session import get_db
from app.core.logger import logger

router = APIRouter()
workflow_service = WorkflowService()


class CreateWorkflowRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    requirement: StructuredRequirement
    status: str = Field(default="PARSED")


class WorkflowResponse(BaseModel):
    # Allow direct serialization of SQLAlchemy ORM Workflow instances
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt: str
    parsed_requirement: Optional[Dict[str, Any]] = None
    workflow_definition: Optional[Dict[str, Any]] = None
    status: str
    error: Optional[str] = None
    execution_metadata: Optional[Dict[str, Any]] = None
    created_at: Any = None
    updated_at: Any = None


# ---------------------------------------------------------------------------
# Phase 2: AI Requirement Understanding
# ---------------------------------------------------------------------------

@router.post(
    "/parse",
    response_model=RequirementParseResponse,
    summary="Parse natural language requirement into structured workflow specification",
    status_code=status.HTTP_200_OK,
)
async def parse_requirement(
    payload: RequirementParseRequest,
    db: AsyncSession = Depends(get_db),
) -> RequirementParseResponse:
    """
    Analyzes natural language business data requests using AI
    and converts them into a strict, validated workflow specification.
    """
    try:
        requirement, workflow_id = await workflow_service.parse_requirement(
            prompt=payload.prompt,
            db=db,
        )

        return RequirementParseResponse(
            success=True,
            requirement=requirement,
            workflow_id=workflow_id,
            clarification_needed=requirement.clarification_needed if requirement.is_ambiguous else None,
            error=None,
        )

    except LLMAuthenticationError as auth_err:
        logger.error(f"AI Provider Authentication failure: {auth_err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Provider is not configured or authenticated. Please verify server API key settings.",
        )

    except LLMTimeoutError as timeout_err:
        logger.error(f"AI Provider Timeout: {timeout_err}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI Provider request timed out. Please try again in a few moments.",
        )

    except RequirementParsingError as parse_err:
        logger.warning(f"Requirement Parsing failed: {parse_err}")
        return RequirementParseResponse(
            success=False,
            requirement=None,
            workflow_id=None,
            clarification_needed="Unable to understand this requirement. Please provide more specific details.",
            error="Unable to understand this requirement. Please try again.",
        )

    except Exception as exc:
        logger.error(f"Unexpected server error during parse: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while analyzing the requirement. Please try again.",
        )


# ---------------------------------------------------------------------------
# Phase 3: Workflow Planning & Execution
# ---------------------------------------------------------------------------

@router.post(
    "/plan",
    response_model=PlanWorkflowResponse,
    summary="Generate deterministic workflow execution plan from structured requirement",
    status_code=status.HTTP_200_OK,
)
async def plan_workflow(
    payload: PlanWorkflowRequest,
    db: AsyncSession = Depends(get_db),
) -> PlanWorkflowResponse:
    """
    Translates a structured requirement from Phase 2 into a validated,
    deterministic workflow DAG plan with ordered steps and dependencies.
    """
    try:
        workflow_def = await workflow_service.plan_workflow(
            requirement=payload.requirement,
            prompt=payload.prompt,
            workflow_id=payload.workflow_id,
            db=db,
        )
        return PlanWorkflowResponse(
            success=True,
            workflow=workflow_def,
            error=None,
        )
    except WorkflowValidationError as val_err:
        logger.warning(f"Workflow plan validation failed: {val_err}")
        return PlanWorkflowResponse(
            success=False,
            workflow=None,
            error=f"Validation failed: {str(val_err)}",
        )
    except Exception as e:
        logger.error(f"Workflow planning unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to generate workflow plan: {str(e)}",
        )


@router.post(
    "/{workflow_id}/execute",
    response_model=ExecuteWorkflowResponse,
    summary="Execute planned workflow using mock step executors",
    status_code=status.HTTP_200_OK,
)
async def execute_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExecuteWorkflowResponse:
    """
    Runs the workflow's dependency graph step by step using Phase 3 mock executors.
    Updates step states (PENDING -> RUNNING -> COMPLETED / FAILED) and persists outcomes.
    """
    try:
        executed_def = await workflow_service.execute_workflow(
            workflow_id=workflow_id,
            db=db,
        )
        return ExecuteWorkflowResponse(
            success=True,
            workflow=executed_def,
            error=executed_def.error,
        )
    except WorkflowStateError as se:
        logger.warning(f"Workflow execution state conflict: {se}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(se),
        )
    except ValueError as ve:
        logger.warning(f"Workflow execution not found or invalid: {ve}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}",
        )


@router.post(
    "/{workflow_id}/resume",
    response_model=ExecuteWorkflowResponse,
    summary="Resume a workflow paused for human action",
    status_code=status.HTTP_200_OK,
)
async def resume_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExecuteWorkflowResponse:
    """
    Resumes a PAUSED workflow after the human completes the required action
    (e.g. a CAPTCHA), continuing from the paused step instead of restarting.
    """
    try:
        resumed_def = await workflow_service.resume_workflow(workflow_id=workflow_id, db=db)
        return ExecuteWorkflowResponse(
            success=True,
            workflow=resumed_def,
            error=resumed_def.error,
        )
    except WorkflowStateError as se:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(se),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Workflow resume failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow resume failed: {str(e)}",
        )


@router.get(
    "/{workflow_id}/steps",
    response_model=WorkflowStepsResponse,
    summary="Get workflow steps and current execution states",
    status_code=status.HTTP_200_OK,
)
async def get_workflow_steps(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStepsResponse:
    """
    Retrieves the ordered steps, execution states, outputs, and errors for a specific workflow.
    """
    workflow_def = await workflow_service.get_workflow_definition(workflow_id=workflow_id, db=db)
    if not workflow_def:
        # Check if record exists without definition
        record = await workflow_service.get_workflow_by_id(workflow_id=workflow_id, db=db)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow with ID '{workflow_id}' not found.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow '{workflow_id}' has not been planned yet. Call /plan first.",
        )

    return WorkflowStepsResponse(
        workflow_id=workflow_def.workflow_id,
        status=workflow_def.status,
        steps=workflow_def.steps,
    )


# ---------------------------------------------------------------------------
# Workflow Persistence & Listing Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=WorkflowResponse,
    summary="Create or confirm a workflow specification",
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    payload: CreateWorkflowRequest,
    db: AsyncSession = Depends(get_db),
):
    """Saves and confirms a parsed workflow in the database."""
    try:
        workflow = await workflow_service.create_workflow(
            prompt=payload.prompt,
            requirement=payload.requirement,
            db=db,
            status=payload.status,
        )
        return workflow
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save workflow specification.",
        )


@router.get(
    "",
    response_model=List[WorkflowResponse],
    summary="List recent workflows",
)
async def list_workflows(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves list of recently parsed workflows."""
    try:
        return await workflow_service.list_recent_workflows(db=db, limit=limit)
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return []


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Get workflow details by ID",
)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves a single workflow by ID."""
    workflow = await workflow_service.get_workflow_by_id(workflow_id=workflow_id, db=db)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return workflow
