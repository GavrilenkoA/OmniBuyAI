import json

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL
from .models import Product
from .retrieval import retrieve_products

_client = OpenAI(api_key=OPENAI_API_KEY)


def analyze_request(user_query: str, conversation_history: list[dict] | None = None) -> dict:
    """Analyze user query: either extract params or ask clarifying questions."""
    messages = [
        {
            "role": "system",
            "content": (
                "Ты — умный помощник для планирования покупок продуктов в супермаркете.\n"
                "Пользователь описывает что ему нужно — это может быть что угодно:\n"
                "- 'Собери продукты на неделю для семьи из 4 человек'\n"
                "- 'Хочу приготовить борщ'\n"
                "- 'Нужны продукты для похудения на 5 дней'\n"
                "- 'Закупка для пикника на 10 человек'\n"
                "- 'Что-нибудь на ужин, я один'\n\n"
                "Твоя задача — понять запрос и определить, достаточно ли информации.\n\n"
                "Если информации ДОСТАТОЧНО, верни JSON:\n"
                '{"status": "ready", "params": {"days": int, "people": int, '
                '"preferences": "описание предпочтений/ограничений", '
                '"budget": float|null, "context": "краткое описание задачи"}}\n\n'
                "Если информации НЕДОСТАТОЧНО — задай ОДИН уточняющий вопрос:\n"
                '{"status": "need_info", "question": "вопрос"}\n\n'
                "ПРАВИЛА:\n"
                "- Не спрашивай лишнего. Если можно разумно предположить — предполагай.\n"
                "- 'Хочу борщ' → достаточно: 1 день, 1 человек, предпочтения='борщ'.\n"
                "- Спрашивай только если запрос действительно неясен.\n"
                "- Учитывай ВСЮ историю диалога."
            ),
        },
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_query})

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=messages,
    )
    return json.loads(response.choices[0].message.content)


def generate_meal_plan(params: dict) -> list[dict]:
    """Generate a meal plan for the given parameters."""
    context = params.get("context", "")
    preferences = params.get("preferences", "сбалансированное питание")

    prompt = (
        f"Составь план питания на {params.get('days', 3)} дней "
        f"для {params.get('people', 2)} человек.\n"
        f"Предпочтения: {preferences}.\n"
    )
    if context:
        prompt += f"Контекст: {context}\n"
    if params.get("budget"):
        prompt += f"Бюджет: {params['budget']}₽.\n"

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
                    "Каждое блюдо — 1-3 слова, название рецепта."
                ),
            },
            {"role": "user", "content": prompt},
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
    query = ", ".join(dishes)
    candidates = retrieve_products(query, products, top_k=30)

    catalog_text = "\n".join(
        f"ID:{p.internal_id} | {p.category} | {p.title} | {p.price}₽"
        + (f" | скидка {p.discount}" if p.discount else "")
        + f" | рейтинг:{p.rating} отзывы:{p.review_count}"
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
                    "Тебе даны блюда и каталог доступных товаров.\n"
                    "Выбери товары и количества для приготовления блюд.\n"
                    "ПРАВИЛА ВЫБОРА:\n"
                    "- Предпочитай товары с высоким рейтингом и большим кол-вом отзывов\n"
                    "- При прочих равных предпочитай товары со скидкой\n"
                    "- quantity — кол-во упаковок (целое число, минимум 1)\n"
                    "- Выбирай ТОЛЬКО товары из каталога\n"
                    '- Верни JSON: {"products": [{"internal_id": int, "quantity": int}, ...]}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Блюда: {', '.join(dishes)}\n"
                    f"Людей: {people}\n\n"
                    f"Каталог:\n{catalog_text}"
                ),
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return [(item["internal_id"], item["quantity"]) for item in data["products"]]


def adjust_for_nutrition(
    current_products: list[tuple[int, int]],
    issues: list[str],
    products: list[Product],
) -> list[tuple[int, int]]:
    """Ask LLM to adjust product quantities to fix nutrition imbalances."""
    product_map = {p.internal_id: p for p in products}

    current_text = "\n".join(
        f"ID:{pid} | {product_map[pid].title} | qty:{qty} | {product_map[pid].price}₽"
        for pid, qty in current_products
        if pid in product_map
    )

    issue_query = " ".join(issues)
    extra_candidates = retrieve_products(issue_query, products, top_k=15)
    extra_text = "\n".join(
        f"ID:{p.internal_id} | {p.category} | {p.title} | {p.price}₽ | "
        f"рейтинг:{p.rating} отзывы:{p.review_count}"
        for p in extra_candidates
    )

    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — диетолог. Скорректируй набор продуктов.\n"
                    "Предпочитай товары с высоким рейтингом и отзывами.\n"
                    'Верни JSON: {"products": [{"internal_id": int, "quantity": int}, ...]}\n'
                    "quantity=0 означает убрать товар."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Проблемы:\n" + "\n".join(f"- {i}" for i in issues) + "\n\n"
                    f"Текущие товары:\n{current_text}\n\n"
                    f"Дополнительные товары:\n{extra_text}"
                ),
            },
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return [(item["internal_id"], item["quantity"]) for item in data["products"] if item["quantity"] > 0]
