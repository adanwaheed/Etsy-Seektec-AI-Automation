"""Structured output models for Seektec's POD Etsy listing generator."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PersonalizationField(BaseModel):
    """One Etsy-style custom option field generated from the visible design."""

    field_title: str = Field(description="Buyer-facing field title, maximum 45 characters.")
    instructions: str = Field(description="Buyer-facing example/instructions, maximum 120 characters.")
    required: bool = Field(default=True, description="Whether Etsy buyer must fill the field.")
    detected_type: str = Field(
        default="text",
        description="Classification such as name, initials, monogram, text, date, number, or color.",
    )

    @field_validator("field_title", "instructions", "detected_type")
    @classmethod
    def clean_text(cls, value: str) -> str:
        # Preserve instruction line breaks but normalize accidental repeated spaces.
        if "\n" in value:
            return "\n".join(" ".join(line.split()) for line in value.splitlines()).strip()
        return " ".join(value.split()).strip()


class PODListingDraft(BaseModel):
    """Gemini-generated Etsy listing data for a POD apparel product."""

    design_subject: str = Field(description="Short generic summary of what the design shows.")
    detected_text: list[str] = Field(default_factory=list, description="Readable text found in the design.")
    design_themes: list[str] = Field(default_factory=list, description="Relevant visual themes/styles.")
    title: str = Field(description="Clear, buyer-friendly Etsy title, maximum 140 characters.")
    tags: list[str] = Field(description="Exactly 13 unique Etsy tags, each 20 characters or fewer.")
    personalization_fields: list[PersonalizationField] = Field(
        default_factory=list,
        description="Up to 5 Etsy-style custom option fields; empty when personalization is disabled.",
    )
    personalization_summary: str = Field(
        default="",
        description="Short explanation of what Gemini detected as customizable, only when enabled.",
    )
    ip_warnings: list[str] = Field(
        default_factory=list,
        description="Possible readable brands, characters, teams, celebrity names, lyrics, or other IP concerns.",
    )

    @field_validator("title", "design_subject", "personalization_summary")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            tag = " ".join(value.lower().strip().strip("#,. ").split())
            if tag:
                cleaned.append(tag)
        return cleaned


class ValidationReport(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
