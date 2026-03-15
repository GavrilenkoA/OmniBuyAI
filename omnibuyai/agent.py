from .cart_builder import build_cart
from .data_loader import load_products
from .models import Product
from .nutrition import calculate_nutrition, check_balance
from .planner import (
    adjust_for_nutrition,
    analyze_request,
    generate_meal_plan,
    select_products_for_dishes,
)


class GroceryAgent:
    def __init__(self):
        self.products: list[Product] = []
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        print("📦 Загрузка каталога товаров...")
        self.products = load_products()
        print(f"   Загружено {len(self.products)} товаров")
        self._loaded = True

    def clarify(self, user_query: str, conversation_history: list[dict] | None = None) -> dict:
        """Analyze the query. Returns {"status": "ready", "params": ...} or {"status": "need_info", "question": ...}."""
        print("🧠 Анализ запроса...")
        result = analyze_request(user_query, conversation_history)

        if result["status"] == "ready":
            params = result["params"]
            print(
                f"   Дней: {params.get('days', '?')}, "
                f"Человек: {params.get('people', '?')}, "
                f"Предпочтения: {params.get('preferences', '-')}"
            )
        else:
            print(f"   ❓ Нужно уточнение")

        return result

    def execute(self, params: dict) -> dict:
        """Execute the meal planning and cart building with resolved params."""
        self._ensure_loaded()

        days = params.get("days", 3)
        people = params.get("people", 2)

        # Generate meal plan
        print("📋 Составление плана питания...")
        meal_plan = generate_meal_plan(params)

        # Select products for each meal
        print("🛒 Подбор товаров...")
        all_product_selections: list[tuple[int, int]] = []

        for day_plan in meal_plan:
            day_num = day_plan["day"]
            for meal in day_plan["meals"]:
                meal_type = meal["meal_type"]
                dishes = meal["dishes"]
                print(f"   День {day_num}, {meal_type}: {', '.join(dishes)}")
                selections = select_products_for_dishes(dishes, self.products, people)
                all_product_selections.extend(selections)

        # Check nutrition balance
        print("⚖️  Проверка баланса КБЖУ...")
        product_map = {p.id: p for p in self.products}
        products_with_qty = [
            (product_map[pid], qty)
            for pid, qty in all_product_selections
            if pid in product_map
        ]

        nutrition = calculate_nutrition(products_with_qty, days, people)
        balance = check_balance(nutrition)

        # Adjust if needed
        if not balance["balanced"]:
            print("🔄 Корректировка для баланса КБЖУ...")
            for issue in balance["issues"]:
                print(f"   ⚠️  {issue}")

            all_product_selections = adjust_for_nutrition(
                all_product_selections, balance["issues"], self.products
            )

            products_with_qty = [
                (product_map[pid], qty)
                for pid, qty in all_product_selections
                if pid in product_map
            ]
            nutrition = calculate_nutrition(products_with_qty, days, people)
            balance = check_balance(nutrition)

        # Build cart
        print("🛍️  Формирование корзины...")
        cart = build_cart(all_product_selections, self.products)
        total_price = sum(item.price * item.quantity for item in cart)

        return {
            "meal_plan": meal_plan,
            "cart": [item.model_dump() for item in cart],
            "nutrition": nutrition.model_dump(),
            "balance": balance,
            "total_price": round(total_price, 2),
            "params": params,
        }
