import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("GROQ_API_KEY", "")

if not LLM_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY не задан. Добавьте его в .env файл:\n"
        "  GROQ_API_KEY=gsk_..."
    )

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
