# Seektec POD Etsy Listing Studio

A Gemini-powered, Vercel-ready internal tool for Seektec's print-on-demand apparel listings.

## What this version does

Inputs:
- Product/design image
- Product type: Sweatshirt, T-Shirt, Hoodie, Cap, Quarter-Zip Sweatshirt
- Design method: Print or Embroidery
- Personalization: Yes / No
- Target audience
- Design placement
- Product color
- Occasion/theme
- Optional confirmed notes

Outputs:
- Etsy-ready, buyer-friendly SEO title
- Exactly 13 Etsy tags (each <= 20 characters)
- Design read: subject, visible wording, themes
- Personalization changes + ready-to-paste Etsy personalization field only when Personalization = Yes
- Possible IP review warnings

Removed from the older project:
- AliExpress URL/data
- Long product description generation
- Shipping/returns sections
- Jewelry-specific workflow
- Product material/dimensions fields

## Gemini API

1. Copy `.env.example` to `.env` (a placeholder `.env` is included for local convenience).
2. Add your Gemini API key:

   `GEMINI_API_KEY=your_real_key`

Never commit `.env` to GitHub. Add the key in Vercel under Project > Settings > Environment Variables.

## Run locally (Windows)

Double-click `start.bat`, or run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Deploy to Vercel

Push the folder to GitHub, import the repo into Vercel, and add these environment variables:

- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash`
- `GEMINI_FALLBACK_MODELS=gemini-2.5-flash-lite`
- `GEMINI_RETRY_ATTEMPTS=3`
- `GEMINI_TIMEOUT_SECONDS=120`
- `MAX_UPLOAD_MB=3`

The frontend automatically compresses large images before upload to reduce Vercel 413 payload errors.

## Etsy SEO behavior

The prompt follows current Etsy-style best practices: clear item naming, readable titles rather than keyword stuffing, and all 13 varied multi-word tags. It cannot guarantee ranking or sales; shop quality, conversion, price, photos, reviews, shipping and other factors also matter.

## Branding

- Seektec logo appears in the top-left and footer.
- Footer credit: **Made by Adan Waheed**.
