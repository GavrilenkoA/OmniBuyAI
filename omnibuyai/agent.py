import logging
from collections.abc import Callable

from .cart_builder import build_cart
from .data_loader import load_products
from .models import Product
from .planner import (
    analyze_request,
    generate_meal_plan,
    select_products_for_day,
)
from .retrieval import rank_available

logger = logging.getLogger(__name__)

AvailabilityChecker = Callable[[list[int]], set[int]]


class GroceryAgent:
    def __init__(self, check_availability: AvailabilityChecker | None = None):
        """
        Args:
            check_availability: sync callback: list[internal_id] → set[available_ids].
                If None, all candidates are assumed available.
        """
        self.products: list[Product] = []
        self._loaded = False
        self._check_availability = check_availability

    def _ensure_loaded(self):
        if self._loaded:
            return
        self.products = load_products()
        logger.info("Загружено %d товаров", len(self.products))
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

    def get_all_candidate_ids(self, params: dict) -> tuple[dict, list[dict]]:
        """Phase 1: generate meal plan + candidates (1 LLM call per day).

        Returns:
            (partial_result, candidate_groups)
        """
        self._ensure_loaded()
        people = params.get("people", 2)

        logger.info("Составление плана питания...")
        meal_plan = generate_meal_plan(params)
        logger.info("План: %d дней", len(meal_plan))

        # One LLM call per day (not per meal)
        logger.info("Подбор кандидатов товаров...")
        all_candidate_groups: list[dict] = []

        for day_plan in meal_plan:
            day_dishes = []
            for meal in day_plan["meals"]:
                day_dishes.extend(meal["dishes"])

            logger.info("  День %d: %s", day_plan["day"], ", ".join(day_dishes))
            groups = select_products_for_day(day_dishes, self.products, people)

            for g in groups:
                logger.info("    → %s: %d кандидатов, qty=%d",
                            g["role"], len(g["candidates"]), g["quantity"])
            all_candidate_groups.extend(groups)

        all_ids = list({pid for g in all_candidate_groups for pid in g["candidates"]})
        logger.info("Всего уникальных кандидатов: %d", len(all_ids))

        return {
            "meal_plan": meal_plan,
            "params": params,
            "all_candidate_ids": all_ids,
        }, all_candidate_groups

    def finalize_cart(
        self,
        candidate_groups: list[dict],
        available_ids: set[int],
        meal_plan: list[dict],
        params: dict,
    ) -> dict:
        """Phase 2: given availability, pick best products and build cart."""
        self._ensure_loaded()
        product_map = {p.internal_id: p for p in self.products}

        final_selections: list[tuple[int, int]] = []
        unavailable_roles: list[str] = []

        for group in candidate_groups:
            best_id = rank_available(group["candidates"], available_ids, product_map)
            if best_id is not None:
                p = product_map[best_id]
                logger.info("  ✅ %s → %s (ID:%d)", group["role"], p.title, best_id)
                final_selections.append((best_id, group["quantity"]))
            else:
                unavailable_roles.append(group["role"])
                logger.warning("  ❌ %s → нет доступных", group["role"])

        cart_items = build_cart(final_selections, self.products)
        total_price = sum(item.price * item.quantity for item in cart_items)
        cart = {item.internal_id: item.quantity for item in cart_items}

        logger.info("Корзина: %d позиций, %.2f₽", len(cart), total_price)

        result = {
            "cart": cart,
            "meal_plan": meal_plan,
            "total_price": round(total_price, 2),
            "params": params,
        }

        if unavailable_roles:
            result["unavailable"] = unavailable_roles

        return result

    def execute(self, params: dict) -> dict:
        """Build a grocery cart (sync, with optional availability check)."""
        partial, groups = self.get_all_candidate_ids(params)

        if self._check_availability:
            logger.info("Проверка наличия через callback...")
            available_ids = self._check_availability(partial["all_candidate_ids"])
            logger.info("Доступно %d из %d", len(available_ids), len(partial["all_candidate_ids"]))
        else:
            available_ids = set(partial["all_candidate_ids"])

        return self.finalize_cart(groups, available_ids, partial["meal_plan"], params)

    def run(self, user_query: str) -> dict:
        """Full pipeline: clarify → execute.

        If the query is unclear, returns need_info instead of a cart.
        """
        result = self.clarify(user_query)

        if result["status"] == "need_info":
            return result

        return self.execute(result["params"])
