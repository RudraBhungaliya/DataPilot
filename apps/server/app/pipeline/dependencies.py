"""
Shared, process-wide Phase 5 data pipeline singleton.

Ensures the workflow executors and the dataset APIs read/write the same
in-memory record and dataset store.
"""

from functools import lru_cache

from app.pipeline.service import DataPipelineService


@lru_cache(maxsize=1)
def get_data_service() -> DataPipelineService:
    """Returns the single shared DataPipelineService for the process."""
    return DataPipelineService()
