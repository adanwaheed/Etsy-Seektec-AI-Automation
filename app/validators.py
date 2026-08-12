"""Deterministic Etsy formatting checks for Seektec POD output."""

from __future__ import annotations

from .schemas import PODListingDraft, ValidationReport


def validate_listing(listing: PODListingDraft, personalization: str, decoration_method: str = "") -> ValidationReport:
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

    enabled = personalization.strip().lower() == "yes"
    fields = listing.personalization_fields

    if not enabled:
        if fields or listing.personalization_summary.strip():
            errors.append("Personalization output must be empty when Personalization is set to No.")
    else:
        if not fields:
            errors.append("Personalization is enabled, but no custom-option fields were generated.")
        if len(fields) > 5:
            errors.append(f"Etsy custom options support up to 5 fields; received {len(fields)}.")

        for idx, field in enumerate(fields, start=1):
            if len(field.field_title) > 45:
                errors.append(f"Personalization field {idx} title is over 45 characters.")
            if len(field.instructions) > 120:
                errors.append(f"Personalization field {idx} instructions are over 120 characters.")
            if not field.field_title.strip():
                errors.append(f"Personalization field {idx} has an empty title.")
            if not field.instructions.strip():
                errors.append(f"Personalization field {idx} has empty instructions.")

        expected_color_title = (
            "Choose Embroidery Thread Colors"
            if decoration_method.strip().lower() == "embroidery"
            else "Choose Print Colors"
        )
        color_fields = [f for f in fields if f.detected_type.strip().lower() == "color" or f.field_title == expected_color_title]
        exact = [f for f in fields if f.field_title == expected_color_title]
        if len(exact) != 1:
            errors.append(f'Personalization must contain exactly one color field titled "{expected_color_title}".')
        elif not exact[0].instructions.startswith("E.g:"):
            errors.append("Color customization instructions must begin with 'E.g:'.")
        if len(color_fields) > 1:
            warnings.append("More than one field appears to request colors; review for duplication.")

        if not listing.personalization_summary.strip():
            warnings.append("No personalization detection summary was generated.")

    if listing.ip_warnings:
        warnings.append("Review possible intellectual-property terms before publishing on Etsy.")

    score = 100 - 15 * len(errors) - 4 * len(warnings)
    score = max(0, min(100, score))
    return ValidationReport(passed=not errors, score=score, errors=errors, warnings=warnings)
