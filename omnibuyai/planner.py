import json

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL
from .models import Product
from .retrieval import retrieve_products

_client = OpenAI(api_key=OPENAI_API_KEY)


def parse_request(user_query: str) -> dict:
    """Extract structured parameters from user query."""
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — помощник для планирования покупок продуктов. "
                    "Извлеки из запроса пользователя параметры в JSON:\n"
                    '{"days": int, "people": int, "preferences": str, "budget": float|null}\n'
                    "preferences — любые пожелания по питанию (вегетарианское, сбалансированное, etc). "
                    "Если параметр не указан, используй разумные значения по умолчанию: "
                    "days=3, people=2, preferences='сбалансированное питание', budget=null."
                ),
            },
            {"role": "user", "content": user_query},
        ],
    )
    return json.loads(response.choices[0].message.content)


def generate_meal_plan(params: dict) -> list[dict]:
    """Generate a meal plan for the given parameters."""
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — диетолог-повар. Составь план питания.\n"
                    "Верни JSON:\n"
                    '{"meal_plan": [{"day": 1, "meals": [{"meal_type": "breakfast", "dishes": ["Овсянка с ягодами", ...]}, '
                    '{"meal_type": "lunch", "dishes": [...]}, {"meal_type": "dinner", "dishes": [...]}]}, ...]}\n'
                    "Блюда должны быть простыми, из доступных в обычном супермаркете продуктов. "
                    "Учитывай сбалансированность по БЖУ. Каждое блюдо — 1-3 слова, название рецепта."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Составь план питания на {params['days']} дней для {params['people']} человек. "
                    f"Предпочтения: {params.get('preferences', 'сбалансированное питание')}."
                ),
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return data["meal_plan"]


def select_products_for_dishes(
    dishes: list[str],
    products: list[Product],
    people: int,
) -> list[tuple[int, int]]:
    """For a list of dishes, retrieve and select matching products with quantities."""
    # Retrieve relevant products for all dishes at once
    query = ", ".join(dishes)
    candidates = retrieve_products(query, products, top_k=30)

    catalog_text = "\n".join(
        f"ID:{p.id} | {p.category} | {p.name} | {p.price}₽ | "
        f"ккал:{p.calories} Б:{p.proteins} Ж:{p.fats} У:{p.carbs} (на 100г)"
        for p in candidates
    )

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — помощник по подбору продуктов из каталога супермаркета.\n"
                    "Тебе даны блюда, которые нужно приготовить, и каталог доступных товаров.\n"
                    "Выбери конкретные товары и их количества для приготовления этих блюд.\n"
                    "quantity — количество упаковок товара (целое число, минимум 1).\n"
                    'Верни JSON: {"products": [{"id": int, "quantity": int}, ...]}\n'
                    "Выбирай только товары из предоставленного каталога. "
                    "Учитывай количество людей при расчёте порций."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Блюда для приготовления: {', '.join(dishes)}\n"
                    f"Количество людей: {people}\n\n"
                    f"Каталог товаров:\n{catalog_text}"
                ),
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return [(item["id"], item["quantity"]) for item in data["products"]]


def adjust_for_nutrition(
    current_products: list[tuple[int, int]],
    issues: list[str],
    products: list[Product],
) -> list[tuple[int, int]]:
    """Ask LLM to adjust product quantities to fix nutrition imbalances."""
    product_map = {p.id: p for p in products}

    current_text = "\n".join(
        f"ID:{pid} | {product_map[pid].name} | qty:{qty} | "
        f"ккал:{product_map[pid].calories} Б:{product_map[pid].proteins} "
        f"Ж:{product_map[pid].fats} У:{product_map[pid].carbs} (на 100г)"
        for pid, qty in current_products
        if pid in product_map
    )

    # Get some additional candidates
    issue_query = " ".join(issues)
    extra_candidates = retrieve_products(issue_query, products, top_k=15)
    extra_text = "\n".join(
        f"ID:{p.id} | {p.category} | {p.name} | {p.price}₽ | "
        f"ккал:{p.calories} Б:{p.proteins} Ж:{p.fats} У:{p.carbs} (на 100г)"
        for p in extra_candidates
    )

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — диетолог. Текущий набор продуктов имеет проблемы с балансом КБЖУ.\n"
                    "Скорректируй количества или добавь/убери товары, чтобы исправить проблемы.\n"
                    'Верни JSON: {"products": [{"id": int, "quantity": int}, ...]}\n'
                    "quantity=0 означает убрать товар."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Проблемы:\n" + "\n".join(f"- {i}" for i in issues) + "\n\n"
                    f"Текущие товары:\n{current_text}\n\n"
                    f"Дополнительные доступные товары:\n{extra_text}"
                ),
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return [(item["id"], item["quantity"]) for item in data["products"] if item["quantity"] > 0]
