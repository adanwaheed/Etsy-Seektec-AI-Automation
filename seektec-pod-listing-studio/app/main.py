"""FastAPI app for Seektec POD Etsy Listing Studio."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .generator import PODGenerationError, generate_pod_listing
from .validators import validate_listing

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TEMP_DIR = Path(tempfile.gettempdir()) / "seektec-pod"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Vercel rejects function request payloads above its platform limit before FastAPI runs.
# The browser compresses images before upload; this backend limit is a second safety net.
_requested_mb = float(os.getenv("MAX_UPLOAD_MB", "3"))
MAX_UPLOAD_MB = min(_requested_mb, 3.2) if os.getenv("VERCEL") else _requested_mb
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_PRODUCTS = {
    "Sweatshirt",
    "T-Shirt",
    "Hoodie",
    "Cap",
    "Quarter-Zip Sweatshirt",
}
SUPPORTED_METHODS = {"Print", "Embroidery"}

app = FastAPI(
    title="Seektec POD Etsy Listing Studio",
    version="1.0.0",
    description="AI-assisted Etsy title, tag, and personalization generator for Seektec POD apparel.",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


async def _save_image(upload: UploadFile) -> Path:
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG, or WebP image.")
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The compressed image is still too large. Keep it below {MAX_UPLOAD_MB:.1f} MB.",
        )
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[upload.content_type]
    path = TEMP_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(content)
    return path


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"max_upload_mb": MAX_UPLOAD_MB},
    )


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "company": "Seektec",
        "provider": "Google Gemini",
        "vercel": bool(os.getenv("VERCEL")),
    }


@app.post("/api/generate")
async def generate(
    image: UploadFile = File(...),
    product_type: str = Form(...),
    decoration_method: str = Form(...),
    personalization: str = Form("No"),
    target_audience: str = Form(""),
    placement: str = Form(""),
    product_color: str = Form(""),
    occasion_theme: str = Form(""),
    notes: str = Form(""),
) -> JSONResponse:
    if product_type not in SUPPORTED_PRODUCTS:
        raise HTTPException(status_code=400, detail="Choose a supported Seektec product type.")
    if decoration_method not in SUPPORTED_METHODS:
        raise HTTPException(status_code=400, detail="Decoration method must be Print or Embroidery.")
    personalization = "Yes" if personalization.strip().lower() == "yes" else "No"

    path = await _save_image(image)
    try:
        listing = generate_pod_listing(
            path,
            mime_type=image.content_type,
            product_type=product_type,
            decoration_method=decoration_method,
            personalization=personalization,
            target_audience=target_audience,
            placement=placement,
            product_color=product_color,
            occasion_theme=occasion_theme,
            notes=notes,
        )
        report = validate_listing(listing, personalization)
        return JSONResponse(
            {
                "listing": listing.model_dump(),
                "validation": report.model_dump(),
                "inputs": {
                    "product_type": product_type,
                    "decoration_method": decoration_method,
                    "personalization": personalization,
                    "target_audience": target_audience,
                    "placement": placement,
                    "product_color": product_color,
                    "occasion_theme": occasion_theme,
                },
            }
        )
    except PODGenerationError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    finally:
        path.unlink(missing_ok=True)
