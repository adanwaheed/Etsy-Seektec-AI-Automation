from app.schemas import PODListingDraft, PersonalizationField
from app.validators import validate_listing


def base_listing():
    return PODListingDraft(
        design_subject="heart memorial design",
        detected_text=["The Heart Never Forgets", "Jennifer"],
        design_themes=["memorial", "heart"],
        title="Embroidered Memorial Heart Sweatshirt, Personalized Name Crewneck",
        tags=[
            "memorial sweatshirt", "embroidered shirt", "memory gift", "heart sweatshirt",
            "personalized top", "name embroidery", "memorial crewneck", "remembrance gift",
            "custom sweatshirt", "heart embroidery", "gift for her", "memory shirt", "embroidered gift",
        ],
        personalization_fields=[],
        personalization_summary="",
        ip_warnings=[],
    )


def test_non_personalized_listing_passes():
    listing = base_listing()
    report = validate_listing(listing, "No", "Embroidery")
    assert report.passed
    assert len(listing.tags) == 13


def test_personalized_embroidery_requires_color_field():
    listing = base_listing()
    listing.personalization_fields = [
        PersonalizationField(field_title="Provide Name", instructions="E.g: Adan", detected_type="name")
    ]
    listing.personalization_summary = "Detected a customizable name."
    report = validate_listing(listing, "Yes", "Embroidery")
    assert not report.passed
    assert any("Choose Embroidery Thread Colors" in error for error in report.errors)


def test_personalized_embroidery_fields_pass():
    listing = base_listing()
    listing.personalization_fields = [
        PersonalizationField(field_title="Provide Name", instructions="E.g: Adan", detected_type="name"),
        PersonalizationField(
            field_title="Choose Embroidery Thread Colors",
            instructions="E.g:\nName (Red)\nMain Graphic (White)",
            detected_type="color",
        ),
    ]
    listing.personalization_summary = "Detected a name and separate graphic color elements."
    report = validate_listing(listing, "Yes", "Embroidery")
    assert report.passed


def test_print_uses_print_color_title():
    listing = base_listing()
    listing.personalization_fields = [
        PersonalizationField(field_title="Provide Custom Text", instructions="E.g: Booked and Busy", detected_type="text"),
        PersonalizationField(field_title="Choose Print Colors", instructions="E.g:\nText (Purple)\nGraphic (White)", detected_type="color"),
    ]
    listing.personalization_summary = "Detected editable text and graphic colors."
    report = validate_listing(listing, "Yes", "Print")
    assert report.passed
