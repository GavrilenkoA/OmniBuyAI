import logging

from .cart_builder import build_cart
from .data_loader import load_products
from .models import Product
from .planner import (
    analyze_request,
    generate_meal_plan,
    select_products_for_dishes,
)

logger = logging.getLogger(__name__)


class GroceryAgent:
    def __init__(self):
        self.products: list[Product] = []
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self.products = load_products()
        logger.info("Загружено %d товаров (in_stock)", len(self.products))
        self._loaded = True

    def clarify(self, user_query: str, conversation_history: list[dict] | None = None) -> dict:
        """Analyze the query.

        Returns:
            {"status": "ready", "params": {...}}
            or
            {"status": "need_info", "question": "..."}
        """
        result = analyze_request(user_query, conversation_history)
        logger.info("Анализ запроса: %s", result.get("status"))
        return result

    def execute(self, params: dict) -> dict:
        """Build a grocery cart from resolved params.

        Returns:
            {
                "cart": {internal_id: quantity, ...},
                "meal_plan": [...],
                "total_price": float,
                "params": {...},
            }
        """
        self._ensure_loaded()

        people = params.get("people", 2)

        # Generate meal plan
        logger.info("Составление плана питания...")
        meal_plan = generate_meal_plan(params)

        # Select products for each meal
        logger.info("Подбор товаров...")
        all_selections: list[tuple[int, int]] = []

        for day_plan in meal_plan:
            for meal in day_plan["meals"]:
                selections = select_products_for_dishes(meal["dishes"], self.products, people)
                all_selections.extend(selections)

        # Build cart
        cart_items = build_cart(all_selections, self.products)
        total_price = sum(item.price * item.quantity for item in cart_items)

        # Output: {internal_id: quantity}
        cart = {item.internal_id: item.quantity for item in cart_items}

        return {
            "cart": cart,
            "meal_plan": meal_plan,
            "total_price": round(total_price, 2),
            "params": params,
        }

    def run(self, user_query: str) -> dict:
        """Full pipeline: clarify (non-interactive) → execute.

        If the query is unclear, returns need_info instead of a cart.
        For interactive clarification use clarify() + execute() separately.
        """
        result = self.clarify(user_query)

        if result["status"] == "need_info":
            return result

        return self.execute(result["params"])
