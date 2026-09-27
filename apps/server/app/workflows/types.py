"""
Workflow Engine Enumerations and Types.
Defines valid lifecycle statuses and executable step types.
"""

from enum import Enum


class WorkflowStatus(str, Enum):
    """Lifecycle statuses for a workflow."""
    DRAFT = "DRAFT"
    PARSED = "PARSED"  # Legacy compatibility with Phase 2
    CONFIRMED = "CONFIRMED"  # Legacy compatibility with Phase 2
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Execution status for an individual workflow step."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepType(str, Enum):
    """Categorized step types supported by the Workflow Engine."""
    PARSE_REQUIREMENT = "PARSE_REQUIREMENT"
    DISCOVER_SOURCES = "DISCOVER_SOURCES"
    COLLECT_DATA = "COLLECT_DATA"
    EXTRACT_DATA = "EXTRACT_DATA"
    NORMALIZE_DATA = "NORMALIZE_DATA"
    VALIDATE_DATA = "VALIDATE_DATA"
    DEDUPLICATE_DATA = "DEDUPLICATE_DATA"
    BUILD_DATASET = "BUILD_DATASET"
    EXPORT_DATA = "EXPORT_DATA"
