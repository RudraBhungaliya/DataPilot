"""
Workflow Execution Engine.
Executes DAG workflows according to dependency graph order with state tracking.
"""

from typing import Optional, Callable, Awaitable, Dict, Any, List
from datetime import datetime, timezone
from app.workflows.types import WorkflowStatus, StepStatus
from app.workflows.schemas import WorkflowDefinition, WorkflowStep
from app.workflows.validator import WorkflowValidator
from app.workflows.registry import ExecutorRegistry, get_default_registry
from app.workflows.executors.base import ExecutionContext
from app.core.logger import logger


StepCallback = Callable[[WorkflowDefinition, WorkflowStep], Awaitable[None]]


class WorkflowEngine:
    """
    Core workflow orchestrator responsible for executing step graphs.
    """

    def __init__(self, registry: Optional[ExecutorRegistry] = None):
        self.registry = registry or get_default_registry()

    async def execute(
        self,
        workflow: WorkflowDefinition,
        on_step_update: Optional[StepCallback] = None,
    ) -> WorkflowDefinition:
        """
        Executes a workflow definition across its dependency graph.

        :param workflow: The WorkflowDefinition to run
        :param on_step_update: Optional async callback invoked on step state transitions
        :return: Updated WorkflowDefinition with step results and final status
        """
        # 1. Validate workflow structure and obtain topological execution order
        try:
            execution_order: List[str] = WorkflowValidator.validate(workflow)
        except Exception as val_err:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = f"Workflow validation failed prior to execution: {str(val_err)}"
            logger.error(workflow.error)
            return workflow

        # 2. Transition workflow status to RUNNING
        workflow.status = WorkflowStatus.RUNNING
        workflow.updated_at = datetime.now(timezone.utc).isoformat()
        if not workflow.created_at:
            workflow.created_at = workflow.updated_at

        step_map: Dict[str, WorkflowStep] = {s.id: s for s in workflow.steps}
        context = ExecutionContext(
            workflow_id=workflow.workflow_id,
            input_requirement=workflow.input_requirement,
            metadata={"started_at": workflow.updated_at},
        )

        logger.info(
            f"Starting workflow execution: {workflow.workflow_id} "
            f"({len(workflow.steps)} steps, order: {' -> '.join(execution_order)})"
        )

        failed = False
        failed_step_id: Optional[str] = None

        # 3. Execute steps in topological dependency order
        for step_id in execution_order:
            step = step_map[step_id]

            if failed:
                # Upstream failure: skip remaining dependent steps
                step.status = StepStatus.SKIPPED
                step.metadata["skipped_reason"] = f"Upstream dependency failure at '{failed_step_id}'"
                if on_step_update:
                    await on_step_update(workflow, step)
                continue

            # Check if any dependencies failed or were skipped
            dep_failed = any(
                step_map[dep].status in [StepStatus.FAILED, StepStatus.SKIPPED]
                for dep in step.depends_on
            )
            if dep_failed:
                step.status = StepStatus.SKIPPED
                step.metadata["skipped_reason"] = "Prerequisite steps did not complete successfully"
                if on_step_update:
                    await on_step_update(workflow, step)
                continue

            # Transition step to RUNNING
            step.status = StepStatus.RUNNING
            step_start_time = datetime.now(timezone.utc)
            step.metadata["started_at"] = step_start_time.isoformat()
            if on_step_update:
                await on_step_update(workflow, step)

            # Retrieve executor from registry
            try:
                executor = self.registry.get(step.type)
            except Exception as reg_err:
                step.status = StepStatus.FAILED
                step.error = f"Executor resolution error: {str(reg_err)}"
                workflow.status = WorkflowStatus.FAILED
                workflow.error = f"Step '{step.name}' failed: {step.error}"
                failed = True
                failed_step_id = step.id
                if on_step_update:
                    await on_step_update(workflow, step)
                continue

            # Prepare step input by aggregating outputs from immediate dependencies
            step_input: Dict[str, Any] = {
                dep: context.get_step_output(dep) for dep in step.depends_on
            }
            step.input = step_input

            # Execute the step
            try:
                result = await executor.execute(step=step, context=context)
                step_end_time = datetime.now(timezone.utc)
                duration_ms = int((step_end_time - step_start_time).total_seconds() * 1000)

                if result.success:
                    step.status = StepStatus.COMPLETED
                    step.output = result.output
                    step.metadata.update(result.metadata)
                    step.metadata["completed_at"] = step_end_time.isoformat()
                    step.metadata["duration_ms"] = duration_ms

                    # Record output into context for subsequent steps
                    context.step_outputs[step.id] = result.output
                    logger.info(f"Step '{step.name}' ({step.id}) completed successfully in {duration_ms}ms")
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.error or "Step executor returned failure without message."
                    step.metadata.update(result.metadata)
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = f"Step '{step.name}' failed: {step.error}"
                    failed = True
                    failed_step_id = step.id
                    logger.warning(f"Step '{step.name}' ({step.id}) failed: {step.error}")

            except Exception as exec_err:
                step.status = StepStatus.FAILED
                step.error = f"Unexpected execution error: {str(exec_err)}"
                workflow.status = WorkflowStatus.FAILED
                workflow.error = f"Step '{step.name}' failed: {step.error}"
                failed = True
                failed_step_id = step.id
                logger.error(f"Step '{step.name}' encountered exception: {exec_err}", exc_info=True)

            if on_step_update:
                await on_step_update(workflow, step)

        # 4. Finalize overall workflow status
        if not failed:
            workflow.status = WorkflowStatus.COMPLETED
            workflow.error = None
            logger.info(f"Workflow '{workflow.workflow_id}' completed all steps successfully.")

        workflow.updated_at = datetime.now(timezone.utc).isoformat()
        return workflow
