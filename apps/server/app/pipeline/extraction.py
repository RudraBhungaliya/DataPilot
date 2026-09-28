"""
Extraction engine for Phase 5.

Turns raw documents into structured records using a deterministic JSON
fast-path and an LLM fallback for unstructured HTML/text.
"""

import json
from typing import Any, Dict, List, Optional

from app.ai.provider import LLMProvider, LLMError, get_llm_provider
from app.collection.schemas import RawDocument
from app.core.config import settings
from app.core.logger import logger
from app.pipeline.schemas import ExtractionRecord

# Maximum characters of a document included in an LLM extraction prompt.
_MAX_PROMPT_CHARS = 12000

# Substrings that indicate a placeholder rather than a real API key.
_PLACEHOLDER_KEY_MARKERS = ("your_", "changeme", "example", "placeholder", "test_key", "xxx")


def _llm_key_configured() -> bool:
    key = (settings.effective_ai_api_key or "").strip()
    if not key:
        return False
    lowered = key.lower()
    return not any(marker in lowered for marker in _PLACEHOLDER_KEY_MARKERS)

EXTRACTION_SYSTEM_PROMPT = """You are DataPilot's structured data extraction engine.
Given the raw content of a single web document, extract every distinct record matching the target entity.

Rules:
1. Extract ONLY information present in the content. Never invent values.
2. Return a JSON object of the form {"records": [ {..}, {..} ]}.
3. Each record is a flat JSON object whose keys are the requested fields (snake_case).
4. Use null for a requested field that is not present in the content.
5. If the content contains no valid record, return {"records": []}.
"""


def build_extraction_prompt(entity: str, required_fields: List[str], content: str) -> str:
    fields = ", ".join(required_fields) if required_fields else "any relevant attributes"
    snippet = content[:_MAX_PROMPT_CHARS]
    return (
        f"Target entity: {entity}\n"
        f"Requested fields: {fields}\n\n"
        f"<document_content>\n{snippet}\n</document_content>\n\n"
        f"Extract all records as JSON."
    )


class JSONExtractor:
    """Deterministic extractor for JSON payloads."""

    _LIST_KEYS = ("records", "results", "items", "data", "companies", "jobs", "startups", "entries")

    def extract(self, content: str, entity: str, required_fields: List[str]) -> List[ExtractionRecord]:
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return []

        items = self._items(payload)
        records: List[ExtractionRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            records.append(
                ExtractionRecord(
                    entity=entity,
                    data=self._project(item, required_fields),
                    extraction_method="deterministic_json",
                    confidence=0.9,
                )
            )
        return records

    def _items(self, payload: Any) -> List[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in self._LIST_KEYS:
                value = payload.get(key)
                if isinstance(value, list):
                    return value
            return [payload]
        return []

    @staticmethod
    def _project(item: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Keeps requested fields plus other scalar attributes (drops nested noise)."""
        if not required_fields:
            return {k: v for k, v in item.items() if not isinstance(v, (dict, list))}

        projected: Dict[str, Any] = {}
        for field in required_fields:
            if field in item:
                projected[field] = item[field]
        for key, value in item.items():
            if key not in projected and not isinstance(value, (dict, list)):
                projected[key] = value
        return projected


class LLMExtractor:
    """LLM-backed extractor for unstructured HTML/text content."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider

    def _get_provider(self) -> LLMProvider:
        return self._provider or get_llm_provider()

    async def extract(self, content: str, entity: str, required_fields: List[str]) -> List[ExtractionRecord]:
        if self._provider is None and not _llm_key_configured():
            logger.info("LLM provider not configured (placeholder/absent key); skipping LLM extraction.")
            return []

        provider = self._get_provider()
        prompt = build_extraction_prompt(entity, required_fields, content)
        payload = await provider.generate_json(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
        )

        if not isinstance(payload, dict):
            return []
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            # Tolerate a model returning a single record object directly
            raw_records = [payload] if payload else []

        records: List[ExtractionRecord] = []
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            confidence = item.get("_confidence")
            if not isinstance(confidence, (int, float)):
                confidence = 0.8
            records.append(
                ExtractionRecord(
                    entity=entity,
                    data=item,
                    extraction_method="llm",
                    confidence=float(confidence),
                )
            )
        return records


class ExtractionEngine:
    """
    Chooses the extraction strategy per document:
    deterministic JSON first, LLM fallback for unstructured content.
    """

    def __init__(
        self,
        json_extractor: Optional[JSONExtractor] = None,
        llm_extractor: Optional[LLMExtractor] = None,
    ):
        self.json_extractor = json_extractor or JSONExtractor()
        self.llm_extractor = llm_extractor or LLMExtractor()

    async def extract_document(
        self,
        document: RawDocument,
        entity: str,
        required_fields: List[str],
    ) -> List[ExtractionRecord]:
        content = document.content or ""
        if not content.strip():
            return []

        content_type = (document.content_type or "").lower()
        looks_like_json = ("json" in content_type) or content.lstrip()[:1] in ("{", "[")

        if looks_like_json:
            records = self.json_extractor.extract(content, entity, required_fields)
            if records:
                return [self._stamp(r, document, "deterministic_json") for r in records]

        try:
            records = await self.llm_extractor.extract(content, entity, required_fields)
            return [self._stamp(r, document, "llm") for r in records]
        except LLMError as err:
            logger.warning(f"LLM extraction failed for document {document.document_id}: {err}")
            return []
        except Exception as err:  # resilience: extraction must not abort the pipeline
            logger.error(f"Unexpected extraction error for document {document.document_id}: {err}", exc_info=True)
            return []

    @staticmethod
    def _stamp(record: ExtractionRecord, document: RawDocument, method: str) -> ExtractionRecord:
        record.extraction_method = method
        record.source_document_id = document.document_id
        record.source_id = document.source_id
        record.source_url = document.url or document.canonical_url
        record.collection_job_id = document.job_id
        return record
