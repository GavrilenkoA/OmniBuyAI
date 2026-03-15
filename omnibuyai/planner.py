import json

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL
from .models import Product
from .retrieval import retrieve_products

_client = OpenAI(api_key=OPENAI_API_KEY)

CANDIDATES_PER_PRODUCT = 3


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


def select_product_candidates(
    dishes: list[str],
    products: list[Product],
    people: int,
    candidates_per_product: int = CANDIDATES_PER_PRODUCT,
) -> list[dict]:
    """For each required product, select multiple candidates for availability check.

    Returns list of:
        {"role": "молоко", "candidates": [internal_id, ...], "quantity": int}
    """
    query = ", ".join(dishes)
    candidates = retrieve_products(query, products, top_k=50)

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
                    "Тебе даны блюда и каталог товаров.\n"
                    "Для каждого необходимого ингредиента выбери НЕСКОЛЬКО кандидатов "
                    f"(до {candidates_per_product} штук) — похожих товаров, которые могут заменить друг друга.\n"
                    "Это нужно на случай, если часть товаров окажется недоступна.\n\n"
                    "ПРАВИЛА:\n"
                    "- Первый кандидат — лучший (высокий рейтинг, много отзывов, скидка)\n"
                    "- Остальные — альтернативы из той же категории\n"
                    "- quantity — кол-во упаковок (целое число, минимум 1)\n"
                    "- Выбирай ТОЛЬКО товары из каталога\n"
                    '- Верни JSON: {"products": [{"role": "описание ингредиента", '
                    f'"candidates": [id1, id2, ...до {candidates_per_product}], '
                    '"quantity": int}, ...]}'
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
    return data["products"]
