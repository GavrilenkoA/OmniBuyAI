from .cart_builder import build_cart
from .data_loader import load_products
from .models import CartItem, NutritionSummary, Product
from .nutrition import calculate_nutrition, check_balance
from .planner import (
    adjust_for_nutrition,
    generate_meal_plan,
    parse_request,
    select_products_for_dishes,
)
from .retrieval import build_embeddings


class GroceryAgent:
    def __init__(self):
        self.products: list[Product] = []

    def run(self, user_query: str) -> dict:
        # 1. Load products
        print("📦 Загрузка каталога товаров...")
        self.products = load_products()
        print(f"   Загружено {len(self.products)} товаров")

        # 2. Build embeddings if needed
        print("🔍 Подготовка поискового индекса...")
        build_embeddings(self.products)

        # 3. Parse user request
        print("🧠 Анализ запроса...")
        params = parse_request(user_query)
        days = params.get("days", 3)
        people = params.get("people", 2)
        preferences = params.get("preferences", "сбалансированное питание")
        print(f"   Дней: {days}, Человек: {people}, Предпочтения: {preferences}")

        # 4. Generate meal plan
        print("📋 Составление плана питания...")
        meal_plan = generate_meal_plan(params)

        # 5. Select products for each day's meals
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

        # 6. Check nutrition balance
        print("⚖️  Проверка баланса КБЖУ...")
        product_map = {p.id: p for p in self.products}
        products_with_qty = [
            (product_map[pid], qty)
            for pid, qty in all_product_selections
            if pid in product_map
        ]

        nutrition = calculate_nutrition(products_with_qty, days, people)
        balance = check_balance(nutrition)

        # 7. Adjust if needed
        if not balance["balanced"]:
            print("🔄 Корректировка для баланса КБЖУ...")
            for issue in balance["issues"]:
                print(f"   ⚠️  {issue}")

            all_product_selections = adjust_for_nutrition(
                all_product_selections, balance["issues"], self.products
            )

            # Recalculate nutrition
            products_with_qty = [
                (product_map[pid], qty)
                for pid, qty in all_product_selections
                if pid in product_map
            ]
            nutrition = calculate_nutrition(products_with_qty, days, people)
            balance = check_balance(nutrition)

        # 8. Build cart
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
