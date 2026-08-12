"""Gemini multimodal generation for Seektec POD Etsy titles and tags."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from google.genai import types

from .gemini_client import (
    GeminiConfigurationError,
    GeminiRequestError,
    create_gemini_client,
    generate_content_with_fallback,
)
from .prompts import REPAIR_PROMPT, SYSTEM_PROMPT
from .schemas import PODListingDraft, PersonalizationField
from .validators import validate_listing


class PODGenerationError(RuntimeError):
    """Raised when Gemini cannot generate a valid POD listing."""


def _normalize_personalization(
    listing: PODListingDraft,
    personalization: str,
    decoration_method: str,
) -> PODListingDraft:
    """Apply deterministic Etsy-style field naming and safe limits after Gemini output."""

    if personalization.strip().lower() != "yes":
        listing.personalization_fields = []
        listing.personalization_summary = ""
        return listing

    title_map = {
        "name": "Provide Name",
        "initials": "Provide Initials",
        "monogram": "Provide Monogram",
        "number": "Provide Number",
        "date": "Provide Date / Year",
        "year": "Provide Date / Year",
        "text": "Provide Custom Text",
    }
    examples = {
        "name": "E.g: Adan",
        "initials": "E.g: AW",
        "monogram": "E.g: AWA",
        "number": "E.g: 24",
        "date": "E.g: 2026",
        "year": "E.g: 2026",
        "text": "E.g: Custom Text",
    }
    expected_color_title = (
        "Choose Embroidery Thread Colors"
        if decoration_method.strip().lower() == "embroidery"
        else "Choose Print Colors"
    )

    normalized: list[PersonalizationField] = []
    color_field: PersonalizationField | None = None

    for field in listing.personalization_fields:
        kind = (field.detected_type or "text").strip().lower()
        if kind == "color" or "color" in field.field_title.lower():
            if color_field is None:
                instructions = field.instructions.strip()
                if not instructions.startswith("E.g:"):
                    instructions = "E.g:\n" + instructions
                color_field = PersonalizationField(
                    field_title=expected_color_title,
                    instructions=instructions[:120].rstrip(),
                    required=True,
                    detected_type="color",
                )
            continue

        if len(normalized) >= 4:  # Etsy allows 5 total; reserve one field for colors.
            continue
        canonical = title_map.get(kind, field.field_title.strip() or "Provide Custom Text")
        instruction = field.instructions.strip() or examples.get(kind, "E.g: Custom Text")
        normalized.append(
            PersonalizationField(
                field_title=canonical[:45].rstrip(),
                instructions=instruction[:120].rstrip(),
                required=True,
                detected_type=kind,
            )
        )

    if color_field is None:
        labels: list[str] = []
        for field in normalized:
            kind = field.detected_type.lower()
            labels.append({
                "name": "Name",
                "initials": "Initials",
                "monogram": "Monogram",
                "number": "Number",
                "date": "Date",
                "year": "Year",
                "text": "Text",
            }.get(kind, "Text"))
        if "Main Graphic" not in labels:
            labels.append("Main Graphic")
        sample_colors = ["Red", "White", "Purple", "Black"]
        lines = ["E.g:"] + [f"{label} ({sample_colors[i % len(sample_colors)]})" for i, label in enumerate(labels[:4])]
        instructions = "\n".join(lines)
        color_field = PersonalizationField(
            field_title=expected_color_title,
            instructions=instructions[:120].rstrip(),
            required=True,
            detected_type="color",
        )

    normalized.append(color_field)
    listing.personalization_fields = normalized[:5]
    if not listing.personalization_summary.strip():
        listing.personalization_summary = "Detected editable design elements and matched buyer input fields."
    return listing


def _parse(response: object) -> PODListingDraft:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, PODListingDraft):
        return parsed
    text = getattr(response, "text", "") or ""
    if not text.strip():
        raise PODGenerationError("Gemini returned an empty result.")
    try:
        return PODListingDraft.model_validate_json(text)
    except Exception as exc:
        raise PODGenerationError(f"Gemini returned invalid listing JSON: {exc}") from exc


def _seller_context(**fields: str) -> str:
    lines = []
    for label, value in fields.items():
        cleaned = (value or "").strip()
        if cleaned:
            lines.append(f"{label.replace('_', ' ').title()}: {cleaned}")
    return "\n".join(lines)


def generate_pod_listing(
    image_path: Path,
    *,
    mime_type: str | None,
    product_type: str,
    decoration_method: str,
    personalization: str,
    target_audience: str,
    placement: str,
    product_color: str,
    occasion_theme: str,
    notes: str,
) -> PODListingDraft:
    guessed_mime = mime_type or mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    context = _seller_context(
        product_type=product_type,
        decoration_method=decoration_method,
        personalization=personalization,
        target_audience=target_audience,
        design_placement=placement,
        product_color=product_color,
        occasion_or_theme=occasion_theme,
        seller_notes=notes,
    )
    user_prompt = (
        "Create the Seektec Etsy POD listing data from this image and the seller-confirmed inputs below.\n\n"
        f"SELLER INPUTS\n{context}\n\n"
        "Treat Product Type, Decoration Method, and Personalization as exact seller selections. "
        "Use the image to identify the design subject, readable text, style, profession/hobby, and supported buyer intent."
    )
    image_bytes = image_path.read_bytes()

    try:
        client = create_gemini_client()
        result = generate_content_with_fallback(
            client,
            lambda model: client.models.generate_content(
                model=model,
                contents=[
                    user_prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=guessed_mime),
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.35,
                    response_mime_type="application/json",
                    response_schema=PODListingDraft,
                ),
            ),
        )
        listing = _normalize_personalization(_parse(result.response), personalization, decoration_method)
        report = validate_listing(listing, personalization, decoration_method)

        if report.errors:
            repair = generate_content_with_fallback(
                client,
                lambda model: client.models.generate_content(
                    model=model,
                    contents=(
                        "SELLER INPUTS:\n" + context + "\n\n"
                        "VALIDATION ERRORS:\n- " + "\n- ".join(report.errors) + "\n\n"
                        "CURRENT RESULT:\n" + listing.model_dump_json(indent=2)
                    ),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT + "\n\n" + REPAIR_PROMPT,
                        temperature=0.15,
                        response_mime_type="application/json",
                        response_schema=PODListingDraft,
                    ),
                ),
            )
            listing = _normalize_personalization(_parse(repair.response), personalization, decoration_method)

        return listing
    except PODGenerationError:
        raise
    except (GeminiConfigurationError, GeminiRequestError) as exc:
        raise PODGenerationError(str(exc)) from exc
    except Exception as exc:
        raise PODGenerationError(f"Gemini generation failed: {exc}") from exc
