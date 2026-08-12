from app.schemas import PODListingDraft
from app.validators import validate_listing


def valid_listing():
    return PODListingDraft(
        design_subject="teacher apple design",
        detected_text=["Teacher"],
        design_themes=["teacher"],
        title="Embroidered Teacher Sweatshirt, Classroom Apple Crewneck",
        tags=[
            "teacher sweatshirt", "embroidered shirt", "teacher crewneck", "apple teacher gift",
            "classroom sweater", "teaching gift", "educator sweatshirt", "school teacher top",
            "teacher apparel", "embroidered gift", "teacher life", "school crewneck", "gift for teacher",
        ],
        personalization_options=[],
        personalization_instruction="",
        ip_warnings=[],
    )


def test_valid_listing_passes():
    report = validate_listing(valid_listing(), "No")
    assert report.passed
    assert len(valid_listing().tags) == 13


def test_personalization_must_be_empty_when_no():
    listing = valid_listing()
    listing.personalization_options = ["Name"]
    report = validate_listing(listing, "No")
    assert not report.passed
