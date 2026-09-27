"""
Base Step Executor Abstraction and Execution Context.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from app.workflows.schemas import WorkflowStep
from app.ai.schemas import StructuredRequirement


class ExecutionContext(BaseModel):
    """
    Context passed to step executors during workflow runtime.
    Holds workflow state, configuration, and previous step outputs.
    """
    workflow_id: str
    input_requirement: Union[StructuredRequirement, Dict[str, Any]]
    step_outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs keyed by step ID from earlier dependencies in the DAG",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_step_output(self, step_id: str) -> Optional[Any]:
        """Convenience method to retrieve output of a dependency step."""
        return self.step_outputs.get(step_id)


class StepResult(BaseModel):
    """
    Standardized result returned by all step executors.
    """
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseStepExecutor(ABC):
    """
    Abstract base class for all workflow step executors.
    Guarantees a consistent interface across mock and real pipeline executors.
    """

    @abstractmethod
    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        """
        Executes an individual workflow step.

        :param step: The WorkflowStep definition and configuration
        :param context: The ExecutionContext containing inputs and dependency outputs
        :return: StepResult with execution outcome and data payload
        """
        pass
