import logging
from collections.abc import Callable

from .cart_builder import build_cart
from .data_loader import load_products
from .models import Product
from .planner import (
    analyze_request,
    generate_meal_plan,
    select_product_candidates,
)
from .retrieval import rank_available

logger = logging.getLogger(__name__)


class GroceryAgent:
    def __init__(self, check_availability: Callable[[list[int]], set[int]] | None = None):
        """
        Args:
            check_availability: callback that takes a list of internal_ids
                and returns a set of available internal_ids.
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

    def execute(self, params: dict) -> dict:
        """Build a grocery cart from resolved params.

        Pipeline:
            1. Generate meal plan (LLM)
            2. For each meal → select N candidates per product (LLM + BM25)
            3. Collect all candidate IDs → check_availability(server)
            4. Filter unavailable → rank remaining → pick best
            5. Build cart {internal_id: quantity}

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
        product_map = {p.internal_id: p for p in self.products}

        # 1. Generate meal plan
        logger.info("Составление плана питания...")
        meal_plan = generate_meal_plan(params)

        # 2. Select candidates for each meal
        logger.info("Подбор кандидатов товаров...")
        all_candidate_groups: list[dict] = []  # [{role, candidates, quantity}, ...]

        for day_plan in meal_plan:
            for meal in day_plan["meals"]:
                groups = select_product_candidates(meal["dishes"], self.products, people)
                all_candidate_groups.extend(groups)

        # 3. Collect all unique candidate IDs and check availability
        all_candidate_ids = []
        for group in all_candidate_groups:
            all_candidate_ids.extend(group["candidates"])
        all_candidate_ids = list(set(all_candidate_ids))

        if self._check_availability:
            logger.info("Проверка наличия %d товаров на сервере...", len(all_candidate_ids))
            available_ids = self._check_availability(all_candidate_ids)
            logger.info("Доступно %d из %d", len(available_ids), len(all_candidate_ids))
        else:
            available_ids = set(all_candidate_ids)

        # 4. For each group, pick the best available candidate
        final_selections: list[tuple[int, int]] = []
        unavailable_roles: list[str] = []

        for group in all_candidate_groups:
            best_id = rank_available(group["candidates"], available_ids, product_map)
            if best_id is not None:
                final_selections.append((best_id, group["quantity"]))
            else:
                unavailable_roles.append(group["role"])
                logger.warning("Нет доступных товаров для: %s", group["role"])

        # 5. Build cart
        cart_items = build_cart(final_selections, self.products)
        total_price = sum(item.price * item.quantity for item in cart_items)
        cart = {item.internal_id: item.quantity for item in cart_items}

        result = {
            "cart": cart,
            "meal_plan": meal_plan,
            "total_price": round(total_price, 2),
            "params": params,
        }

        if unavailable_roles:
            result["unavailable"] = unavailable_roles

        return result

    def run(self, user_query: str) -> dict:
        """Full pipeline: clarify (non-interactive) → execute.

        If the query is unclear, returns need_info instead of a cart.
        For interactive clarification use clarify() + execute() separately.
        """
        result = self.clarify(user_query)

        if result["status"] == "need_info":
            return result

        return self.execute(result["params"])
