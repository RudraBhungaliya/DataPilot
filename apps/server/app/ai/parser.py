"""
DataPilot Requirement Parser.
Orchestrates prompt preparation, LLM provider invocation, and Pydantic validation.
"""

from typing import Optional
from pydantic import ValidationError
from app.ai.schemas import StructuredRequirement
from app.ai.prompts import REQUIREMENT_UNDERSTANDING_SYSTEM_PROMPT, build_requirement_user_prompt
from app.ai.provider import (
    LLMProvider,
    get_llm_provider,
    LLMError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMInvalidResponseError,
)
from app.core.logger import logger


class RequirementParsingError(Exception):
    """Domain exception raised when requirement parsing cannot be completed."""
    pass


class RequirementParser:
    """
    Requirement Parser responsible for transforming natural language data requirements
    into validated StructuredRequirement specifications.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or get_llm_provider()

    async def parse(self, prompt: str) -> StructuredRequirement:
        """
        Parses a natural language prompt into a validated StructuredRequirement instance.

        :param prompt: User's business requirement in plain English
        :return: StructuredRequirement pydantic instance
        :raises RequirementParsingError: If parsing or validation fails
        """
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise RequirementParsingError("Prompt cannot be empty or whitespace.")

        user_message = build_requirement_user_prompt(cleaned_prompt)

        try:
            raw_data = await self.provider.generate_json(
                prompt=user_message,
                system_prompt=REQUIREMENT_UNDERSTANDING_SYSTEM_PROMPT,
            )
        except (LLMAuthenticationError, LLMTimeoutError):
            # Let specific provider errors bubble up for appropriate HTTP status code mapping
            raise
        except LLMError as err:
            logger.error(f"LLM Provider invocation failed during requirement parsing: {err}")
            raise RequirementParsingError(str(err))
        except Exception as exc:
            logger.error(f"Unexpected error calling LLM Provider: {exc}")
            raise RequirementParsingError("Internal AI provider processing error.")

        try:
            requirement = StructuredRequirement.model_validate(raw_data)
        except ValidationError as val_err:
            logger.error(f"Pydantic schema validation failed on AI output: {val_err.errors()}")
            raise RequirementParsingError("AI produced an invalid structured requirement schema.")

        # Safety net: DataPilot never blocks on clarification. Any ambiguity signal is
        # converted into a recorded assumption so the pipeline always proceeds.
        if requirement.is_ambiguous:
            if requirement.clarification_needed:
                requirement.assumptions = list(requirement.assumptions) + [requirement.clarification_needed]
            requirement.is_ambiguous = False
            requirement.clarification_needed = None

        return requirement
