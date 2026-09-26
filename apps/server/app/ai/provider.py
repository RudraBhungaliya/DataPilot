"""
LLM Provider Abstraction for DataPilot.
Provides a pluggable interface to interact with Gemini, OpenAI, or other future LLMs.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import httpx
from app.core.config import settings
from app.core.logger import logger


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when API key is missing or invalid."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when the LLM provider call times out."""
    pass


class LLMInvalidResponseError(LLMError):
    """Raised when the LLM produces unparseable or malformed output."""
    pass


class LLMProvider(ABC):
    """Abstract Base Class for LLM Providers."""

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Generate a structured JSON response from the LLM.
        
        :param prompt: User requirement prompt
        :param system_prompt: Dedicated system instruction
        :param temperature: LLM sampling temperature
        :return: Parsed Python dictionary representing the JSON response
        """
        pass


class GeminiProvider(LLMProvider):
    """
    Google Gemini Provider Implementation.
    Uses official google-genai SDK with a resilient httpx fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.effective_ai_api_key
        self.model = model or settings.AI_MODEL or "gemini-2.5-flash"
        self.timeout = float(settings.AI_TIMEOUT_SECONDS or 30)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMAuthenticationError(
                "Gemini API key is not configured. Please provide AI_API_KEY or GEMINI_API_KEY in environment variables."
            )

        # Attempt using google-genai SDK first
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Use client.aio (async client)
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )

            raw_text = response.text or ""
            return self._parse_json_text(raw_text)

        except LLMError:
            raise
        except Exception as sdk_err:
            logger.warning(f"google-genai SDK call failed ({type(sdk_err).__name__}), falling back to direct REST: {sdk_err}")
            return await self._call_rest_api(prompt, system_prompt, temperature)

    async def _call_rest_api(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Direct REST fallback to Gemini API via httpx."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 401 or response.status_code == 403:
                    raise LLMAuthenticationError("Invalid or unauthorized AI API key provided.")
                elif response.status_code == 429:
                    raise LLMError("Rate limit exceeded for AI provider. Please retry in a few moments.")
                elif response.status_code != 200:
                    raise LLMError(f"AI Provider error status {response.status_code}.")

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMInvalidResponseError("AI Provider returned no generation candidates.")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise LLMInvalidResponseError("AI Provider response did not contain text content.")

                return self._parse_json_text(parts[0]["text"])

        except httpx.TimeoutException:
            raise LLMTimeoutError("AI Provider request timed out.")
        except httpx.RequestError as exc:
            raise LLMError(f"Network error connecting to AI provider: {type(exc).__name__}")

    def _parse_json_text(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from model output text."""
        cleaned = text.strip()
        # Handle possible markdown fencing ```json ... ```
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.error(f"Failed to decode JSON from AI output: {err}. Raw text: {text[:200]}")
            raise LLMInvalidResponseError(f"LLM produced malformed JSON: {err.msg}")


class MockProvider(LLMProvider):
    """
    Mock LLM Provider for unit tests and local sandboxing without API keys.
    """

    def __init__(self, mock_response: Optional[Dict[str, Any]] = None):
        self.mock_response = mock_response

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        if self.mock_response is not None:
            return self.mock_response

        # Default smart mock based on prompt text
        p_lower = prompt.lower()
        if "internship" in p_lower:
            return {
                "objective": "Find software engineering internships in India",
                "entity": "job_posting",
                "location": {"country": "India", "state": None, "city": None, "region": None, "raw": "India"},
                "time_constraint": {"type": "posted_within", "value": 7, "unit": "days", "raw_text": "last 7 days"},
                "required_fields": ["company_name", "role", "location", "salary", "application_url"],
                "filters": [],
                "source_preferences": [],
                "output_format": "table",
                "confidence_score": 0.99,
                "is_ambiguous": False,
                "clarification_needed": None,
            }
        elif "cybersecurity" in p_lower:
            return {
                "objective": "Find cybersecurity companies in India",
                "entity": "company",
                "location": {"country": "India", "state": None, "city": None, "region": None, "raw": "India"},
                "time_constraint": None,
                "required_fields": ["company_name", "industry", "headquarters", "website", "employee_count"],
                "filters": [{"field": "industry", "operator": "contains", "value": "cybersecurity"}],
                "source_preferences": [],
                "output_format": "table",
                "confidence_score": 0.95,
                "is_ambiguous": False,
                "clarification_needed": None,
            }
        
        return {
            "objective": f"Extract structured data for: {prompt[:50]}",
            "entity": "data_record",
            "location": None,
            "time_constraint": None,
            "required_fields": ["name", "description", "source_url"],
            "filters": [],
            "source_preferences": [],
            "output_format": "table",
            "confidence_score": 0.9,
            "is_ambiguous": False,
            "clarification_needed": None,
        }


def get_llm_provider(provider_type: Optional[str] = None) -> LLMProvider:
    """
    Factory function to retrieve configured LLM Provider.
    Supported: 'gemini', 'mock'.
    """
    provider_name = (provider_type or settings.AI_PROVIDER or "gemini").strip().lower()

    if provider_name == "mock":
        return MockProvider()
    elif provider_name == "gemini":
        return GeminiProvider()
    else:
        logger.warning(f"Unknown AI_PROVIDER '{provider_name}', defaulting to GeminiProvider.")
        return GeminiProvider()
