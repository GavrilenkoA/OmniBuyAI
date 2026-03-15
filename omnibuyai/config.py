import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY не задан. Добавьте его в .env файл:\n"
        "  OPENAI_API_KEY=sk-proj-..."
    )

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Nutrition norms per person per day
DAILY_CALORIES = 2000
DAILY_PROTEINS = (80, 120)   # grams
DAILY_FATS = (60, 80)        # grams
DAILY_CARBS = (200, 300)     # grams
