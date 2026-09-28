"""
Workflow Validation Layer.
Enforces structural integrity, dependency graph validity, and cycle detection.
"""

from typing import List, Dict, Set
from collections import deque
from app.workflows.schemas import WorkflowDefinition, WorkflowStep
from app.workflows.types import StepType, StepStatus, WorkflowStatus


class WorkflowValidationError(Exception):
    """Raised when a workflow definition fails structural or dependency validation."""
    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or [message]
        full_msg = f"{message} ({'; '.join(self.errors)})" if self.errors else message
        super().__init__(full_msg)


class WorkflowValidator:
    """
    Validates workflow schemas, dependency references, and detects cyclic dependencies.
    """

    @classmethod
    def validate(cls, workflow: WorkflowDefinition) -> List[str]:
        """
        Validates a WorkflowDefinition and returns the topological execution order of step IDs.

        :param workflow: The WorkflowDefinition to validate
        :return: List of step IDs in topologically sorted execution order
        :raises WorkflowValidationError: If any validation checks fail
        """
        errors: List[str] = []

        # 1. At least one step
        if not workflow.steps:
            errors.append("Workflow must contain at least one step.")
            raise WorkflowValidationError("Workflow validation failed", errors)

        # 2. Check workflow status
        if not isinstance(workflow.status, WorkflowStatus):
            errors.append(f"Invalid workflow status '{workflow.status}'.")

        # 3. Step ID uniqueness and order validation
        step_ids: Set[str] = set()
        step_map: Dict[str, WorkflowStep] = {}

        for step in workflow.steps:
            # Check ID uniqueness
            if step.id in step_ids:
                errors.append(f"Duplicate step ID detected: '{step.id}'.")
            step_ids.add(step.id)
            step_map[step.id] = step

            # Check order
            if step.order < 1:
                errors.append(f"Step '{step.id}' has invalid order {step.order}. Order must be >= 1.")

            # Check step type
            if not isinstance(step.type, StepType):
                errors.append(f"Step '{step.id}' has invalid step type '{step.type}'.")

            # Check step status
            if not isinstance(step.status, StepStatus):
                errors.append(f"Step '{step.id}' has invalid status '{step.status}'.")

            # Check config exists
            if step.config is None or not isinstance(step.config, dict):
                errors.append(f"Step '{step.id}' must provide a valid configuration dictionary.")

        # 4. Check dependencies reference existing steps and no self-dependency
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep == step.id:
                    errors.append(f"Step '{step.id}' cannot depend on itself.")
                elif dep not in step_ids:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep}'.")

        if errors:
            raise WorkflowValidationError("Workflow validation failed with structural errors.", errors)

        # 5. Dependency Graph Cycle Detection via Topological Sort (Kahn's Algorithm)
        in_degree: Dict[str, int] = {step.id: 0 for step in workflow.steps}
        adjacency: Dict[str, List[str]] = {step.id: [] for step in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                adjacency[dep].append(step.id)
                in_degree[step.id] += 1

        # Queue nodes with 0 in-degree (no prerequisites)
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        topological_order: List[str] = []

        while queue:
            curr = queue.popleft()
            topological_order.append(curr)

            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If not all steps are processed, there is at least one cycle
        if len(topological_order) != len(workflow.steps):
            cycle_steps = [sid for sid, deg in in_degree.items() if deg > 0]
            cycle_msg = f"Circular dependency detected involving steps: {', '.join(cycle_steps)}."
            errors.append(cycle_msg)
            raise WorkflowValidationError(cycle_msg, errors)

        return topological_order
