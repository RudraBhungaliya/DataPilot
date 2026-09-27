"""
Step Executor Registry.
Maps StepType to corresponding executor implementations.
"""

from typing import Dict
from app.workflows.types import StepType
from app.workflows.executors.base import BaseStepExecutor
from app.workflows.executors.mock import MockStepExecutor


class UnknownStepTypeError(Exception):
    """Raised when an unregistered StepType is requested from the registry."""
    pass


class ExecutorRegistry:
    """
    Registry maintaining mappings between StepTypes and their executor handlers.
    """

    def __init__(self):
        self._executors: Dict[StepType, BaseStepExecutor] = {}

    def register(self, step_type: StepType, executor: BaseStepExecutor) -> None:
        """
        Registers an executor for a specific StepType.
        """
        self._executors[step_type] = executor

    def get(self, step_type: StepType) -> BaseStepExecutor:
        """
        Retrieves the registered executor for a StepType.

        :raises UnknownStepTypeError: If no executor is registered for the StepType.
        """
        if step_type not in self._executors:
            raise UnknownStepTypeError(
                f"No executor registered for step type: '{step_type}'. "
                f"Available types: {list(self._executors.keys())}"
            )
        return self._executors[step_type]

    def has(self, step_type: StepType) -> bool:
        """Checks if an executor is registered for a StepType."""
        return step_type in self._executors


from app.workflows.executors.discovery import SourceDiscoveryStepExecutor
from app.workflows.executors.collection import CollectionStepExecutor


def get_mock_registry() -> ExecutorRegistry:
    """
    Constructs an ExecutorRegistry with mock executors for all step types.
    Useful for offline testing and isolation.
    """
    registry = ExecutorRegistry()
    mock_executor = MockStepExecutor()
    for step_type in StepType:
        registry.register(step_type, mock_executor)
    return registry


def get_default_registry() -> ExecutorRegistry:
    """
    Constructs and returns the standard ExecutorRegistry for Phase 4.
    - DISCOVER_SOURCES -> SourceDiscoveryStepExecutor (real discovery engine)
    - COLLECT_DATA -> CollectionStepExecutor (real collection engine)
    - Downstream steps -> MockStepExecutor (Phase 5 will implement real extraction)
    """
    registry = ExecutorRegistry()
    mock_executor = MockStepExecutor()

    # Base registration with mock fallback for all downstream steps
    for step_type in StepType:
        registry.register(step_type, mock_executor)

    # Wire Phase 4 real collection engine
    registry.register(StepType.DISCOVER_SOURCES, SourceDiscoveryStepExecutor())
    registry.register(StepType.COLLECT_DATA, CollectionStepExecutor())

    return registry
