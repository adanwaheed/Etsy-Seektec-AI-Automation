"""Structured output models for Seektec's POD Etsy listing generator."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PODListingDraft(BaseModel):
    """Gemini-generated Etsy listing data for a POD apparel product."""

    design_subject: str = Field(description="Short generic summary of what the design shows.")
    detected_text: list[str] = Field(default_factory=list, description="Readable text found in the design.")
    design_themes: list[str] = Field(default_factory=list, description="Relevant visual themes/styles.")
    title: str = Field(description="Clear, buyer-friendly Etsy title, maximum 140 characters.")
    tags: list[str] = Field(description="Exactly 13 unique Etsy tags, each 20 characters or fewer.")
    personalization_options: list[str] = Field(
        default_factory=list,
        description="Design elements that can reasonably be customized, only when personalization is enabled.",
    )
    personalization_instruction: str = Field(
        default="",
        description="Ready-to-paste Etsy personalization box instruction, only when personalization is enabled.",
    )
    ip_warnings: list[str] = Field(
        default_factory=list,
        description="Possible readable brands, characters, teams, celebrity names, lyrics, or other IP concerns.",
    )

    @field_validator("title", "design_subject", "personalization_instruction")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            tag = " ".join(value.lower().strip().strip("#,.").split())
            if tag:
                cleaned.append(tag)
        return cleaned


class ValidationReport(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
