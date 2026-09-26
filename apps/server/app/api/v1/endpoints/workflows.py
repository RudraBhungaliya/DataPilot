"""
Workflows and AI Requirement Parsing Endpoints.
"""

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import (
    RequirementParseRequest,
    RequirementParseResponse,
    StructuredRequirement,
)
from app.ai.parser import RequirementParsingError
from app.ai.provider import LLMAuthenticationError, LLMTimeoutError
from app.services.workflow import WorkflowService
from app.db.session import get_db
from app.core.logger import logger
from pydantic import BaseModel, Field

router = APIRouter()
workflow_service = WorkflowService()


class CreateWorkflowRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    requirement: StructuredRequirement
    status: str = Field(default="PARSED")


class WorkflowResponse(BaseModel):
    id: str
    prompt: str
    parsed_requirement: Optional[Dict[str, Any]]
    status: str
    created_at: Any
    updated_at: Any


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
