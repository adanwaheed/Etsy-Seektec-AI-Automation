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
from .schemas import PODListingDraft
from .validators import validate_listing


class PODGenerationError(RuntimeError):
    """Raised when Gemini cannot generate a valid POD listing."""


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
        listing = _parse(result.response)
        report = validate_listing(listing, personalization)

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
            listing = _parse(repair.response)

        return listing
    except PODGenerationError:
        raise
    except (GeminiConfigurationError, GeminiRequestError) as exc:
        raise PODGenerationError(str(exc)) from exc
    except Exception as exc:
        raise PODGenerationError(f"Gemini generation failed: {exc}") from exc
