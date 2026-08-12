from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

from app.gemini_client import create_gemini_client, generate_content_with_fallback

client = create_gemini_client()
result = generate_content_with_fallback(client, lambda model: client.models.generate_content(model=model, contents="Reply with exactly: Seektec Gemini connected"))
print(result.response.text)
print("Model:", result.model)
