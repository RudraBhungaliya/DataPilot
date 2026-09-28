from typing import List, Optional, Union, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class FilterOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    BETWEEN = "between"


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class FilterRule(BaseModel):
    """Filter condition representing criteria on target entities."""
    field: str = Field(..., description="The target attribute name, e.g., 'salary', 'experience_years', 'founded_year'")
    operator: FilterOperator = Field(default=FilterOperator.EQUALS, description="Comparison operator")
    value: Union[str, int, float, bool, List[Any], None] = Field(..., description="Constraint comparison value")

    @field_validator("operator", mode="before")
    @classmethod
    def normalize_operator(cls, v: Any) -> FilterOperator:
        if isinstance(v, FilterOperator):
            return v
        if isinstance(v, str):
            clean = v.strip().lower().replace(" ", "_").replace("-", "_")
            mapping = {
                ">": FilterOperator.GREATER_THAN,
                ">=": FilterOperator.GREATER_THAN_OR_EQUAL,
                "<": FilterOperator.LESS_THAN,
                "<=": FilterOperator.LESS_THAN_OR_EQUAL,
                "=": FilterOperator.EQUALS,
                "==": FilterOperator.EQUALS,
                "!=": FilterOperator.NOT_EQUALS,
                "gt": FilterOperator.GREATER_THAN,
                "gte": FilterOperator.GREATER_THAN_OR_EQUAL,
                "lt": FilterOperator.LESS_THAN,
                "lte": FilterOperator.LESS_THAN_OR_EQUAL,
                "eq": FilterOperator.EQUALS,
                "neq": FilterOperator.NOT_EQUALS,
                "in": FilterOperator.IN_LIST,
            }
            if clean in mapping:
                return mapping[clean]
            for op in FilterOperator:
                if op.value == clean:
                    return op
        return FilterOperator.EQUALS


class LocationConstraint(BaseModel):
    """Geographic constraints extracted from the requirement."""
    country: Optional[str] = Field(None, description="Country name, e.g., 'India', 'United States'")
    state: Optional[str] = Field(None, description="State or province, e.g., 'California', 'Gujarat'")
    city: Optional[str] = Field(None, description="City name, e.g., 'Ahmedabad', 'San Francisco', 'Bengaluru'")
    region: Optional[str] = Field(None, description="Region or area, e.g., 'Asia-Pacific', 'Remote', 'Europe'")
    raw: Optional[str] = Field(None, description="Raw location string if composite or unparsed")


class TimeConstraint(BaseModel):
    """Time boundaries extracted from the requirement."""
    type: Optional[str] = Field(
        None, 
        description="Type of time constraint, e.g., 'posted_within', 'founded_after', 'founded_before', 'date_range', 'updated_within'"
    )
    value: Optional[Union[int, float, str]] = Field(None, description="Time quantity number or date string")
    unit: Optional[str] = Field(None, description="Unit of time, e.g., 'days', 'weeks', 'months', 'years'")
    start_date: Optional[str] = Field(None, description="ISO formatted start date if bounded")
    end_date: Optional[str] = Field(None, description="ISO formatted end date if bounded")
    raw_text: Optional[str] = Field(None, description="Original natural language time phrase")


class StructuredRequirement(BaseModel):
    """
    Structured Requirement Specification produced by AI Requirement Understanding.
    Strictly parsed and extensible for workflow execution.
    """
    objective: str = Field(..., description="High-level summarized objective in clear English")
    entity: str = Field(..., description="Core target entity type, e.g., 'job_posting', 'company', 'startup', 'sponsor', 'article'")
    location: Optional[LocationConstraint] = Field(default=None, description="Location criteria if specified")
    time_constraint: Optional[TimeConstraint] = Field(default=None, description="Temporal or freshness constraint")
    required_fields: List[str] = Field(
        default_factory=list, 
        description="Attributes requested to be collected (e.g. company_name, role, salary, application_url)"
    )
    filters: List[FilterRule] = Field(
        default_factory=list, 
        description="Specific filtering constraints"
    )
    source_preferences: List[str] = Field(
        default_factory=list, 
        description="Preferred platforms/sources if mentioned (e.g., LinkedIn, GitHub, TechCrunch)"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TABLE, 
        description="Preferred delivery format (table, json, csv)"
    )
    confidence_score: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0, 
        description="Model confidence score in the interpretation"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Best-effort assumptions made when the prompt was vague or incomplete"
    )
    is_ambiguous: bool = Field(
        default=False, 
        description="Whether the prompt is too vague or lacks critical context"
    )
    clarification_needed: Optional[str] = Field(
        default=None, 
        description="Specific clarification question if requirement is ambiguous"
    )

    @field_validator("required_fields", mode="before")
    @classmethod
    def clean_required_fields(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            cleaned = []
            for item in v:
                if isinstance(item, str):
                    s = item.strip().lower().replace(" ", "_")
                    if s and s not in cleaned:
                        cleaned.append(s)
            return cleaned
        return []

    @field_validator("output_format", mode="before")
    @classmethod
    def normalize_output_format(cls, v: Any) -> OutputFormat:
        if isinstance(v, OutputFormat):
            return v
        if isinstance(v, str):
            clean = v.strip().lower()
            for fmt in OutputFormat:
                if fmt.value == clean:
                    return fmt
        return OutputFormat.TABLE


class RequirementParseRequest(BaseModel):
    """API Request payload for requirement parsing."""
    prompt: str = Field(..., min_length=1, max_length=2000, description="Natural language data requirement")

    @field_validator("prompt")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Prompt must not be empty or blank whitespace.")
        return stripped


class RequirementParseResponse(BaseModel):
    """API Response payload for requirement parsing."""
    success: bool = Field(..., description="Whether requirement parsing succeeded")
    requirement: Optional[StructuredRequirement] = Field(None, description="The structured workflow specification")
    workflow_id: Optional[str] = Field(None, description="Draft workflow ID for database persistence")
    clarification_needed: Optional[str] = Field(None, description="Clarification message if input is ambiguous")
    error: Optional[str] = Field(None, description="User-safe error explanation if parsing failed")
