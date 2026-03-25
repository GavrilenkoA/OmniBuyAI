import json

from openai import OpenAI

from .config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
from .models import Product
from .retrieval import retrieve_products

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

CANDIDATES_PER_PRODUCT = 3
# Max BM25 candidates to include in LLM prompt
MAX_CATALOG_SIZE = 20


def analyze_request(user_query: str, conversation_history: list[dict] | None = None) -> dict:
    """Analyze user query: extract params or ask clarifying question."""
    messages = [
        {
            "role": "system",
            "content": (
                "Извлеки параметры из запроса на покупку продуктов. "
                "Верни JSON: {\"status\":\"ready\",\"params\":{\"days\":int,\"people\":int,"
                "\"preferences\":str,\"budget\":float|null,\"context\":str}} "
                "или {\"status\":\"need_info\",\"question\":str} если запрос неясен. "
                "Предполагай разумные значения если можно."
            ),
        },
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_query})

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=messages,
    )
    return json.loads(response.choices[0].message.content)


def generate_meal_plan(params: dict) -> list[dict]:
    """Generate a meal plan."""
    preferences = params.get("preferences", "сбалансированное")
    days = params.get("days", 3)
    people = params.get("people", 2)
    context = params.get("context", "")
    budget = params.get("budget")

    user_msg = f"{days} дней, {people} чел, {preferences}."
    if context:
        user_msg += f" {context}."
    if budget:
        user_msg += f" Бюджет {budget}₽."

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Составь план питания. Верни JSON: "
                    "{\"meal_plan\":[{\"day\":1,\"meals\":[{\"meal_type\":\"breakfast\","
                    "\"dishes\":[\"Овсянка\",...]},{\"meal_type\":\"lunch\",\"dishes\":[...]},"
                    "{\"meal_type\":\"dinner\",\"dishes\":[...]}]},...]}. "
                    "Блюда простые, 1-3 слова."
                ),
            },
            {"role": "user", "content": user_msg},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return data["meal_plan"]


def _compact_catalog(products: list[Product]) -> str:
    """Build a compact catalog string to minimize tokens."""
    lines = []
    for p in products:
        # ~10 tokens per line instead of ~20
        line = f"{p.internal_id}|{p.title}|{p.price}"
        if p.discount:
            line += f"|{p.discount}"
        lines.append(line)
    return "\n".join(lines)


def select_product_candidates(
    dishes: list[str],
    products: list[Product],
    people: int,
    candidates_per_product: int = CANDIDATES_PER_PRODUCT,
) -> list[dict]:
    """Select multiple candidates per ingredient for availability check.

    Returns: [{"role": str, "candidates": [id, ...], "quantity": int}, ...]
    """
    query = ", ".join(dishes)
    candidates = retrieve_products(query, products, top_k=MAX_CATALOG_SIZE)
    catalog = _compact_catalog(candidates)

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Подбери продукты для блюд из каталога. "
                    f"Для каждого ингредиента выбери до {candidates_per_product} кандидатов-заменителей. "
                    "Формат каталога: id|название|цена[|скидка]. "
                    "Верни JSON: {\"products\":[{\"role\":\"ингредиент\","
                    f"\"candidates\":[id1,id2,...до {candidates_per_product}],\"quantity\":int}},...]}}"
                ),
            },
            {
                "role": "user",
                "content": f"Блюда: {', '.join(dishes)}\nЛюдей: {people}\n\n{catalog}",
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return data["products"]


def select_products_for_day(
    day_dishes: list[str],
    products: list[Product],
    people: int,
    candidates_per_product: int = CANDIDATES_PER_PRODUCT,
) -> list[dict]:
    """Select candidates for all dishes of one day in a single LLM call.

    Reduces LLM calls from 3 per day to 1 per day.
    """
    query = ", ".join(day_dishes)
    candidates = retrieve_products(query, products, top_k=MAX_CATALOG_SIZE)
    catalog = _compact_catalog(candidates)

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Подбери продукты для всех блюд дня из каталога. "
                    f"Для каждого ингредиента выбери до {candidates_per_product} кандидатов. "
                    "Формат каталога: id|название|цена[|скидка]. "
                    "Верни JSON: {\"products\":[{\"role\":\"ингредиент\","
                    f"\"candidates\":[id1,...до {candidates_per_product}],\"quantity\":int}},...]}}"
                ),
            },
            {
                "role": "user",
                "content": f"Блюда: {', '.join(day_dishes)}\nЛюдей: {people}\n\n{catalog}",
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return data["products"]
