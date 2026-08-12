# Seektec POD Etsy Listing Studio v2

A Seektec-specific FastAPI + Gemini web app for generating Etsy POD listing assets from a design or mockup image.

## Supported products
- Sweatshirt
- T-Shirt
- Hoodie
- Cap
- Quarter-Zip Sweatshirt
- Print and embroidery designs

## Output
- One Etsy-ready SEO title (validated <= 140 characters)
- Exactly 13 Etsy tags (validated <= 20 characters each)
- AI design read: subject, visible text and themes
- Etsy-style personalization custom-option fields when Personalization is ON

## Smart personalization
When Personalization is ON, Gemini classifies visible editable elements:
- Name -> `Provide Name` / `E.g: Adan`
- Initials -> `Provide Initials`
- Monogram -> `Provide Monogram`
- Other wording -> `Provide Custom Text`
- Number/date when relevant
- Embroidery always adds `Choose Embroidery Thread Colors`
- Print always adds `Choose Print Colors`

The color instructions are generated from actual visible parts, for example:

```text
E.g:
Name (Red)
Main Graphic (White)
```

The app limits personalization to 5 Etsy-style fields, field titles to 45 characters, and instructions to 120 characters.

## Run locally
1. Install Python 3.11, 3.12, or 3.13.
2. Open `.env` and add your Gemini API key.
3. Run `start.bat` on Windows.
4. Open `http://127.0.0.1:8000`.

## Vercel
- Add `GEMINI_API_KEY` in Vercel -> Project -> Settings -> Environment Variables.
- Do not upload a real `.env` to GitHub.
- The browser compresses images before upload to reduce Vercel 413 payload errors.
- Push the project to the GitHub repo connected to Vercel; Vercel will redeploy automatically.

## Security
Never commit a real Gemini API key. If a key has previously been committed or shared, rotate/revoke it and use a new key in Vercel environment variables.
