"""Deterministic Etsy formatting checks."""

from __future__ import annotations

from .schemas import PODListingDraft, ValidationReport


def validate_listing(listing: PODListingDraft, personalization: str) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if not listing.title.strip():
        errors.append("Title is empty.")
    if len(listing.title) > 140:
        errors.append(f"Title is {len(listing.title)} characters; Etsy allows up to 140.")

    if len(listing.tags) != 13:
        errors.append(f"Expected exactly 13 tags, received {len(listing.tags)}.")

    too_long = [tag for tag in listing.tags if len(tag) > 20]
    if too_long:
        errors.append("Tags over 20 characters: " + ", ".join(too_long))

    normalized = [tag.casefold().strip() for tag in listing.tags]
    if len(normalized) != len(set(normalized)):
        errors.append("Duplicate Etsy tags were generated.")

    if personalization.lower() != "yes":
        if listing.personalization_options or listing.personalization_instruction.strip():
            errors.append("Personalization output must be empty when Personalization is set to No.")
    else:
        if not listing.personalization_options:
            warnings.append("Personalization is enabled, but no clearly editable design element was detected.")
        if not listing.personalization_instruction.strip():
            warnings.append("No ready-to-paste personalization instruction was generated.")

    if listing.ip_warnings:
        warnings.append("Review possible intellectual-property terms before publishing on Etsy.")

    score = 100
    score -= 18 * len(errors)
    score -= 5 * len(warnings)
    score = max(0, min(100, score))

    return ValidationReport(passed=not errors, score=score, errors=errors, warnings=warnings)
