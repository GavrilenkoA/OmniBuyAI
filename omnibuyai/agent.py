import logging
from collections.abc import Callable, Awaitable

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

# Type for availability checker: takes list[int], returns set[int]
AvailabilityChecker = Callable[[list[int]], set[int]]
AsyncAvailabilityChecker = Callable[[list[int]], Awaitable[set[int]]]


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

    def _build_cart(
        self,
        params: dict,
        available_ids: set[int] | None = None,
    ) -> dict:
        """Core logic: meal plan → candidates → filter by availability → cart.

        Args:
            params: resolved query params
            available_ids: set of available product IDs (None = all available)

        Returns full result dict.
        """
        self._ensure_loaded()

        people = params.get("people", 2)
        product_map = {p.internal_id: p for p in self.products}

        # 1. Generate meal plan
        logger.info("Составление плана питания...")
        meal_plan = generate_meal_plan(params)
        logger.info("План: %d дней", len(meal_plan))

        # 2. Select candidates for each meal
        logger.info("Подбор кандидатов товаров...")
        all_candidate_groups: list[dict] = []

        for day_plan in meal_plan:
            for meal in day_plan["meals"]:
                dishes = meal["dishes"]
                logger.info("  %s день %d: %s",
                            meal["meal_type"], day_plan["day"], ", ".join(dishes))
                groups = select_product_candidates(dishes, self.products, people)
                for g in groups:
                    logger.info("    → %s: %d кандидатов, qty=%d",
                                g["role"], len(g["candidates"]), g["quantity"])
                all_candidate_groups.extend(groups)

        # 3. Collect all candidate IDs
        all_candidate_ids = list({
            pid for group in all_candidate_groups for pid in group["candidates"]
        })
        logger.info("Всего уникальных кандидатов: %d", len(all_candidate_ids))

        # 4. Check availability
        if available_ids is None:
            if self._check_availability:
                logger.info("Проверка наличия через callback...")
                available_ids = self._check_availability(all_candidate_ids)
                logger.info("Доступно %d из %d", len(available_ids), len(all_candidate_ids))
            else:
                available_ids = set(all_candidate_ids)

        # 5. For each group, pick the best available
        final_selections: list[tuple[int, int]] = []
        unavailable_roles: list[str] = []

        for group in all_candidate_groups:
            best_id = rank_available(group["candidates"], available_ids, product_map)
            if best_id is not None:
                p = product_map[best_id]
                logger.info("  ✅ %s → %s (ID:%d)", group["role"], p.title, best_id)
                final_selections.append((best_id, group["quantity"]))
            else:
                unavailable_roles.append(group["role"])
                logger.warning("  ❌ %s → нет доступных", group["role"])

        # 6. Build cart
        cart_items = build_cart(final_selections, self.products)
        total_price = sum(item.price * item.quantity for item in cart_items)
        cart = {item.internal_id: item.quantity for item in cart_items}

        logger.info("Корзина: %d позиций, %.2f₽", len(cart), total_price)

        result = {
            "cart": cart,
            "meal_plan": meal_plan,
            "total_price": round(total_price, 2),
            "params": params,
            "candidate_groups": all_candidate_groups,
        }

        if unavailable_roles:
            result["unavailable"] = unavailable_roles

        return result

    def execute(self, params: dict) -> dict:
        """Build a grocery cart from resolved params (sync)."""
        return self._build_cart(params)

    def execute_with_availability(
        self,
        params: dict,
        available_ids: set[int],
    ) -> dict:
        """Build cart using pre-checked availability data.

        Use this when the caller has already checked availability
        (e.g. basket_service checked via Perekrestok API).
        """
        return self._build_cart(params, available_ids=available_ids)

    def get_all_candidate_ids(self, params: dict) -> tuple[dict, list[dict]]:
        """Phase 1: generate meal plan + candidates without availability check.

        Returns:
            (result_partial, candidate_groups)
            where result_partial has meal_plan and params,
            and candidate_groups is [{role, candidates, quantity}, ...]
        """
        self._ensure_loaded()

        people = params.get("people", 2)

        logger.info("Составление плана питания...")
        meal_plan = generate_meal_plan(params)
        logger.info("План: %d дней", len(meal_plan))

        logger.info("Подбор кандидатов товаров...")
        all_candidate_groups: list[dict] = []

        for day_plan in meal_plan:
            for meal in day_plan["meals"]:
                dishes = meal["dishes"]
                logger.info("  %s день %d: %s",
                            meal["meal_type"], day_plan["day"], ", ".join(dishes))
                groups = select_product_candidates(dishes, self.products, people)
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

    def run(self, user_query: str) -> dict:
        """Full pipeline: clarify → execute.

        If the query is unclear, returns need_info instead of a cart.
        """
        result = self.clarify(user_query)

        if result["status"] == "need_info":
            return result

        return self.execute(result["params"])
