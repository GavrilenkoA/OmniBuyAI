# OmniBuyAI

AI-powered grocery planning agent that builds a shopping cart from real Perekrestok products based on natural language queries.

HSE Hackathon Project.

## How it works

```
User Query (natural language)
        │
        ▼
┌──────────────────────┐
│  Phase 1: Clarify    │  LLM analyzes the query, extracts parameters
│                      │  (days, people, preferences, budget).
│                      │  If unclear — asks a follow-up question.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Phase 2: Meal Plan  │  LLM generates a meal plan
│  + Candidates        │  (breakfast / lunch / dinner for each day).
│                      │  For each ingredient, BM25 retrieves products
│                      │  from 2500+ catalog, then LLM selects
│                      │  3 candidates per ingredient (ranked by
│                      │  rating, reviews, discount).
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Phase 3: Availability│  All candidate IDs are sent to the
│  Check (Server)      │  Perekrestok API via PUT requests.
│                      │  Server returns actual availability.
│                      │  ✅ 200 = available, ❌ else = unavailable.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Phase 4: Ranking    │  Filter out unavailable products.
│  + Cart Assembly     │  For each ingredient, pick the best
│                      │  available candidate by:
│                      │    1. rating
│                      │    2. review_count
│                      │    3. discount
│                      │    4. price (lower = better)
│                      │  Aggregate into {internal_id: quantity}.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Phase 5: Add to     │  Add remaining quantities to Perekrestok
│  Basket              │  basket (1 unit was already added during
│                      │  availability check).
└──────────────────────┘
```

## Project structure

```
omnibuyai/
├── __init__.py        # Public API: GroceryAgent
├── config.py          # Settings, API keys (from .env)
├── models.py          # Pydantic models (Product, CartItem)
├── data_loader.py     # Load products.csv (2500+ products, no in_stock filter)
├── retrieval.py       # BM25 search + quality ranking + rank_available()
├── planner.py         # LLM: analyze query, meal plan, select 3 candidates per ingredient
├── cart_builder.py    # Deduplicate and aggregate cart items
├── agent.py           # Orchestrator: clarify → candidates → availability → cart
data/
├── products.csv       # 2500+ real Perekrestok products
basket_service.py      # FastAPI service: prompt → LLM → availability check → basket
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
OPENAI_MODEL=gpt-5-nano
EMBEDDING_MODEL=text-embedding-3-small
```

## Usage

### CLI (without availability check)

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

### FastAPI service (with availability check + basket)

```bash
uv run uvicorn basket_service:app --reload --port 8000
```

Then send a POST request:

```bash
curl -X POST http://localhost:8000/basket/build \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Собери ужин на двоих за 3000 рублей",
    "session": {
      "auth_token": "Bearer eyJ...",
      "cookies": {"session": "...", "spid": "..."}
    }
  }'
```

API docs: http://localhost:8000/docs

### As a Python library

```python
from omnibuyai import GroceryAgent

# Without availability check (all candidates assumed available)
agent = GroceryAgent()
result = agent.run("Groceries for 3 days, 2 people")

# With custom availability checker
def my_check(ids: list[int]) -> set[int]:
    # call your server, return available IDs
    return {id for id in ids if is_available(id)}

agent = GroceryAgent(check_availability=my_check)
result = agent.run("Groceries for 3 days, 2 people")

# Two-phase for chat bots
analysis = agent.clarify("Buy some food")
# → {"status": "need_info", "question": "For how many days and people?"}

analysis = agent.clarify("3 days, 2 people", conversation_history=[...])
# → {"status": "ready", "params": {"days": 3, "people": 2, ...}}

result = agent.execute(analysis["params"])

# Three-phase (external availability check)
partial, groups = agent.get_all_candidate_ids(params)
available = my_check(partial["all_candidate_ids"])
result = agent.finalize_cart(groups, available, partial["meal_plan"], params)
```

### Output format

```python
{
    "cart": {426943: 2, 491372: 1},       # {internal_id: quantity}
    "meal_plan": [
        {"day": 1, "meals": [
            {"meal_type": "breakfast", "dishes": ["Oatmeal with berries"]},
            {"meal_type": "lunch", "dishes": ["Chicken soup"]},
            {"meal_type": "dinner", "dishes": ["Buckwheat with cutlets"]}
        ]}
    ],
    "total_price": 3456.78,
    "params": {"days": 3, "people": 2, "preferences": "balanced"},
    "unavailable": ["sour cream"]         # ingredients with no available candidates
}
```
