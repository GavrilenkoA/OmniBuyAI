# OmniBuyAI

AI-powered grocery planning agent that builds a shopping cart from real Perekrestok products based on natural language queries.

HSE Hackathon Project.

## How it works

```
User Query (natural language)
        │
        ▼
┌─────────────────┐
│  1. Clarify      │  LLM analyzes the query, extracts parameters
│                  │  (days, people, preferences, budget).
│                  │  If unclear — asks a follow-up question.
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. Meal Plan    │  LLM generates a meal plan
│                  │  (breakfast / lunch / dinner for each day).
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. Retrieval    │  BM25 full-text search over 2500+ products
│                  │  by title, category, description.
│                  │  Ranking factors: rating, review count, discount.
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. Selection    │  LLM picks specific products and quantities
│                  │  from BM25 candidates. Prefers high-rated
│                  │  products with many reviews and discounts.
└────────┬────────┘
         ▼
┌─────────────────┐
│  5. Cart         │  Aggregates selections, deduplicates,
│                  │  returns {internal_id: quantity} dict.
└─────────────────┘
```

## Project structure

```
omnibuyai/
├── __init__.py        # Public API: GroceryAgent
├── config.py          # Settings, API keys (from .env)
├── models.py          # Pydantic models (Product, CartItem)
├── data_loader.py     # Load products.csv into Product list
├── retrieval.py       # BM25 search with quality-based ranking
├── planner.py         # LLM calls: analyze query, generate meal plan, select products
├── cart_builder.py    # Deduplicate and aggregate cart items
├── agent.py           # Orchestrator: clarify → plan → retrieve → select → cart
data/
├── products.csv       # 2500+ real Perekrestok products
main.py                # CLI entry point
```

## Setup

**Requirements:** Python 3.12+

### 1. Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

After installation, restart your terminal or run `source ~/.bashrc` / `source ~/.zshrc`.

### 2. Clone and install

```bash
git clone git@github.com:GavrilenkoA/OmniBuyAI.git
cd OmniBuyAI

# Install Python 3.12 and project dependencies
uv python install 3.12
uv sync
```

### 3. Configure API key

```bash
cp .env.example .env
# Edit .env and set your OpenAI API key:
#   OPENAI_API_KEY=sk-proj-...
```

### `.env` file

```env
OPENAI_API_KEY=sk-proj-...

# --- Models ---
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

## Usage

### CLI

```bash
# With a query argument
uv run python main.py "Collect groceries for 3 days for 2 people"

# Interactive mode
uv run python main.py

# Examples
uv run python main.py "I want to make borscht for 6 people"
uv run python main.py "Weekly groceries for a family of 4, no pork, budget 5000₽"
uv run python main.py "Something for dinner, just me"
```

If the query is too vague, the agent will ask a clarifying question before proceeding.

### As a Python library

```python
from omnibuyai import GroceryAgent

agent = GroceryAgent()

# One-shot (no interactive clarification)
result = agent.run("Groceries for 3 days, 2 people, balanced diet")

if "cart" in result:
    print(result["cart"])        # {426943: 2, 491372: 1, ...}
    print(result["total_price"]) # 3456.78
    print(result["meal_plan"])   # [{day: 1, meals: [...]}, ...]
else:
    # Query was unclear
    print(result["question"])    # "How many people?"

# Two-phase (for chat bots / interactive UIs)
analysis = agent.clarify("Buy some food")
# → {"status": "need_info", "question": "For how many days and people?"}

analysis = agent.clarify("3 days, 2 people", conversation_history=[...])
# → {"status": "ready", "params": {"days": 3, "people": 2, ...}}

result = agent.execute(analysis["params"])
# → {"cart": {internal_id: qty, ...}, "meal_plan": [...], "total_price": ...}
```

### Output format

```python
{
    "cart": {internal_id: quantity, ...},  # {426943: 2, 491372: 1}
    "meal_plan": [
        {"day": 1, "meals": [
            {"meal_type": "breakfast", "dishes": ["Oatmeal with berries"]},
            {"meal_type": "lunch", "dishes": ["Chicken soup"]},
            {"meal_type": "dinner", "dishes": ["Buckwheat with cutlets"]}
        ]}
    ],
    "total_price": 3456.78,
    "params": {"days": 3, "people": 2, "preferences": "balanced"}
}
```
