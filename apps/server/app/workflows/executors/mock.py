"""
Mock Step Executor for Phase 3.
Provides deterministic, testable placeholder outputs for all workflow step types.
All outputs are clearly marked as mock data.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
from app.workflows.types import StepType
from app.workflows.schemas import WorkflowStep
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult


class MockStepExecutor(BaseStepExecutor):
    """
    Mock executor implementation for Phase 3.
    Simulates real execution stages without making external network calls or scraping.
    """

    MOCK_NOTICE = "MOCK DATA ONLY — Real collection/extraction engine will be connected in Phase 4."

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        """
        Executes step using mock generators based on step type.
        """
        req = context.input_requirement
        entity = req.entity if hasattr(req, "entity") else (req.get("entity") if isinstance(req, dict) else "item")
        fields = req.required_fields if hasattr(req, "required_fields") else (req.get("required_fields", []) if isinstance(req, dict) else [])

        handler_map = {
            StepType.PARSE_REQUIREMENT: self._mock_parse_requirement,
            StepType.DISCOVER_SOURCES: self._mock_discover_sources,
            StepType.COLLECT_DATA: self._mock_collect_data,
            StepType.EXTRACT_DATA: self._mock_extract_data,
            StepType.NORMALIZE_DATA: self._mock_normalize_data,
            StepType.VALIDATE_DATA: self._mock_validate_data,
            StepType.DEDUPLICATE_DATA: self._mock_deduplicate_data,
            StepType.BUILD_DATASET: self._mock_build_dataset,
            StepType.EXPORT_DATA: self._mock_export_data,
        }

        handler = handler_map.get(step.type)
        if not handler:
            return StepResult(
                success=False,
                error=f"No mock handler available for step type '{step.type}'",
                metadata={"is_mock": True},
            )

        try:
            output = handler(step, context, entity, fields)
            return StepResult(
                success=True,
                output=output,
                metadata={
                    "is_mock": True,
                    "mock_marker": "PHASE_3_MOCK",
                    "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            return StepResult(
                success=False,
                error=f"Mock execution failed: {str(e)}",
                metadata={"is_mock": True},
            )

    def _mock_parse_requirement(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "parsed_status": "SUCCESS",
            "entity": entity,
            "fields_identified": fields,
        }

    def _mock_discover_sources(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        source_prefs = step.config.get("source_preferences", [])
        sources = [
            {"source_name": "LinkedIn Talent Hub", "url": "https://linkedin.com/jobs", "confidence": 0.96, "status": "accessible"},
            {"source_name": "Indeed Search Portal", "url": "https://indeed.com", "confidence": 0.91, "status": "accessible"},
            {"source_name": "Wellfound (AngelList)", "url": "https://wellfound.com/jobs", "confidence": 0.88, "status": "accessible"},
        ]
        if source_prefs:
            sources.insert(0, {
                "source_name": f"User Preferred: {source_prefs[0]}",
                "url": f"https://example.com/{source_prefs[0].lower().replace(' ', '_')}",
                "confidence": 0.99,
                "status": "accessible",
            })
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "sources_discovered": len(sources),
            "sources": sources,
        }

    def _mock_collect_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "records_collected": 15,
            "raw_payload_bytes": 104857,
            "status": "COLLECTION_COMPLETE",
            "sources_scraped": 3,
        }

    def _mock_extract_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        # Generate sample records that match the requested fields
        sample_records = []
        company_names = ["Apex AI Systems", "HyperScale Cloud", "DataPulse Labs", "Zenith Mobility", "NeuroFlow"]
        for idx, comp in enumerate(company_names, 1):
            record: Dict[str, Any] = {"_mock_id": f"REC-00{idx}"}
            for f in fields:
                if "company" in f:
                    record[f] = comp
                elif "role" in f or "title" in f:
                    record[f] = f"Software Engineering Intern (Summer {idx})"
                elif "location" in f or "city" in f:
                    record[f] = "Bengaluru, India" if "india" in str(context.input_requirement).lower() else "Remote / Hybrid"
                elif "salary" in f or "stipend" in f:
                    record[f] = f"₹{45 + idx * 5},000 / month"
                elif "url" in f or "link" in f:
                    record[f] = f"https://jobs.example.com/apply/{comp.lower().replace(' ', '-')}-{idx}"
                else:
                    record[f] = f"Mock {f.replace('_', ' ').title()} Value {idx}"
            sample_records.append(record)

        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "records_extracted": len(sample_records),
            "extracted_fields": fields,
            "sample_records": sample_records,
        }

    def _mock_normalize_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "records_normalized": 5,
            "transformations_applied": [
                "Trim whitespace & casing normalization",
                "ISO-8601 timestamp coercion",
                "Geographic entity resolution",
                "Currency string standardization",
            ],
            "normalization_pass_rate": 1.0,
        }

    def _mock_validate_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        filters = step.config.get("filters", [])
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "total_records_evaluated": 5,
            "valid_records": 5,
            "invalid_records": 0,
            "validation_rate": 1.0,
            "rules_evaluated": len(filters) + len(fields),
        }

    def _mock_deduplicate_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        dedupe_keys = step.config.get("deduplication_keys", [])
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "total_input_records": 5,
            "unique_records": 5,
            "duplicates_removed": 0,
            "deduplication_keys_used": dedupe_keys,
        }

    def _mock_build_dataset(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        # Fetch previous extraction output or synthesize
        prev_extract = context.step_outputs.get("step_3", {})
        records = prev_extract.get("sample_records", [])
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "dataset_id": f"ds_mock_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "entity": entity,
            "record_count": len(records) if records else 5,
            "schema_fields": fields,
            "records": records,
            "status": "READY",
        }

    def _mock_export_data(self, step: WorkflowStep, context: ExecutionContext, entity: str, fields: List[str]) -> Dict[str, Any]:
        fmt = step.config.get("format", "csv").lower()
        return {
            "is_mock": True,
            "mock_notice": self.MOCK_NOTICE,
            "export_format": fmt,
            "file_name": f"{entity}_intelligence_export.{fmt}",
            "download_url": f"/api/v1/mock/exports/{entity}_export.{fmt}",
            "file_size_bytes": 4096,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
