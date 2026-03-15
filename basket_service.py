import asyncio
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from omnibuyai import GroceryAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASKET_URL = "https://www.perekrestok.ru/api/customer/1.4.1.0/basket/{id}/plus"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en-GB;q=0.9,en;q=0.8,ru-RU;q=0.7,ru;q=0.6",
    "content-length": "0",
    "origin": "https://www.perekrestok.ru",
    "referer": "https://www.perekrestok.ru/",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
}

DELAY_BETWEEN_REQUESTS = 0.3


# ═══════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════

class UserSession(BaseModel):
    auth_token: str = Field(
        ...,
        description="Заголовок auth из браузера: 'Bearer eyJ...'",
    )
    cookies: dict[str, str] = Field(
        ...,
        description="Все cookies из браузера (DevTools → Application → Cookies)",
    )


class PromptRequest(BaseModel):
    prompt: str = Field(..., description="Промт пользователя")
    session: UserSession

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt": "Собери мне ужин на двоих примерно за 5000 рублей",
                    "session": {
                        "auth_token": "Bearer eyJ...",
                        "cookies": {"session": "...", "spid": "..."}
                    }
                }
            ]
        }
    }


class ItemResult(BaseModel):
    internal_id: int
    iteration: int
    status: str
    http_status: Optional[int] = None
    message: str = ""


class BasketResponse(BaseModel):
    success: bool
    prompt: str
    items_from_llm: dict[int, int]
    total_requests: int
    successful: int
    failed: int
    unavailable_roles: list[str] = []
    details: list[ItemResult]


# ═══════════════════════════════════════════════
# Perekrestok API helpers
# ═══════════════════════════════════════════════

async def check_availability_perekrestok(
    candidate_ids: list[int],
    client: httpx.AsyncClient,
) -> set[int]:
    """Check which products are available by trying to add 1 unit via PUT.

    Returns set of internal_ids that were successfully added.
    """
    logger.info("🔍 Проверка наличия %d кандидатов на сервере Перекрёстка...", len(candidate_ids))
    available = set()

    for pid in candidate_ids:
        url = BASKET_URL.format(id=pid)
        try:
            resp = await client.put(url)
            if resp.status_code in (200, 201, 204):
                available.add(pid)
                logger.info("  ✅ ID:%d — доступен (HTTP %d)", pid, resp.status_code)
            else:
                logger.info("  ❌ ID:%d — недоступен (HTTP %d)", pid, resp.status_code)
        except Exception as e:
            logger.warning("  ❌ ID:%d — ошибка: %s", pid, e)

        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    logger.info("📊 Доступно: %d из %d кандидатов", len(available), len(candidate_ids))
    return available


async def add_to_basket(
    cart: dict[int, int],
    already_added: set[int],
    client: httpx.AsyncClient,
) -> list[ItemResult]:
    """Add final cart items. Skip 1 unit for items already added during availability check."""
    results: list[ItemResult] = []
    logger.info("🛒 Добавление %d позиций в корзину...", len(cart))

    for internal_id, quantity in cart.items():
        remaining = quantity - 1 if internal_id in already_added else quantity

        for i in range(remaining):
            url = BASKET_URL.format(id=internal_id)
            iteration = i + 2 if internal_id in already_added else i + 1

            try:
                resp = await client.put(url)

                if resp.status_code in (200, 201, 204):
                    results.append(ItemResult(
                        internal_id=internal_id,
                        iteration=iteration,
                        status="ok",
                        http_status=resp.status_code,
                        message=f"+1 шт (итого {iteration}/{quantity})",
                    ))
                elif resp.status_code == 401:
                    results.append(ItemResult(
                        internal_id=internal_id,
                        iteration=iteration,
                        status="error",
                        http_status=401,
                        message="Токен истёк — перелогиньтесь на perekrestok.ru",
                    ))
                    logger.error("🔒 Токен истёк, прерываем")
                    return results
                else:
                    body = resp.text[:200] if resp.text else ""
                    results.append(ItemResult(
                        internal_id=internal_id,
                        iteration=iteration,
                        status="error",
                        http_status=resp.status_code,
                        message=body,
                    ))
            except Exception as e:
                results.append(ItemResult(
                    internal_id=internal_id,
                    iteration=i + 1,
                    status="error",
                    message=str(e),
                ))

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    return results


# ═══════════════════════════════════════════════
# FastAPI
# ═══════════════════════════════════════════════

app = FastAPI(
    title="Perekrestok Basket Service",
    description=(
        "Промт → LLM → проверка наличия → корзина Перекрёстка.\n\n"
        "1. LLM выбирает несколько кандидатов на каждый ингредиент\n"
        "2. Кандидаты проверяются на наличие через API Перекрёстка\n"
        "3. Из доступных выбирается лучший (рейтинг, отзывы, скидка)\n"
        "4. Финальные товары добавляются в корзину"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/basket/build",
    response_model=BasketResponse,
    summary="Собрать корзину по промту",
)
async def build_basket(request: PromptRequest):
    logger.info("=" * 60)
    logger.info("📝 Новый запрос: %s", request.prompt)
    logger.info("=" * 60)

    token = request.session.auth_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    headers = {**HEADERS, "auth": token}
    cookies = request.session.cookies

    agent = GroceryAgent()

    # ── Phase 1: LLM — clarify + generate candidates ──
    logger.info("🧠 Phase 1: Анализ запроса через LLM...")
    clarify_result = agent.clarify(request.prompt)

    if clarify_result.get("status") == "need_info":
        question = clarify_result.get("question", "Недостаточно информации")
        logger.warning("❓ LLM запрашивает уточнение: %s", question)
        raise HTTPException(422, f"Уточните запрос: {question}")

    params = clarify_result["params"]
    logger.info("✅ Параметры: дней=%s, людей=%s, предпочтения=%s",
                params.get("days"), params.get("people"), params.get("preferences"))

    logger.info("📋 Phase 1: Генерация плана питания и кандидатов...")
    partial_result, candidate_groups = agent.get_all_candidate_ids(params)

    all_candidate_ids = partial_result["all_candidate_ids"]
    meal_plan = partial_result["meal_plan"]

    logger.info("📦 LLM выбрал %d уникальных кандидатов для %d ингредиентов",
                len(all_candidate_ids), len(candidate_groups))

    # ── Phase 2: Check availability via Perekrestok API ──
    logger.info("🔍 Phase 2: Проверка наличия на сервере...")

    async with httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        timeout=15.0,
    ) as client:

        available_ids = await check_availability_perekrestok(all_candidate_ids, client)

        # ── Phase 3: Pick best available, build cart ──
        logger.info("⚖️ Phase 3: Выбор лучших доступных товаров...")
        result = agent.finalize_cart(candidate_groups, available_ids, meal_plan, params)

        cart = result.get("cart", {})
        unavailable_roles = result.get("unavailable", [])

        if not cart:
            logger.error("🚫 Корзина пуста — все кандидаты недоступны")
            raise HTTPException(
                422, "Все выбранные товары недоступны. Попробуйте другой запрос."
            )

        logger.info("🛒 Финальная корзина: %d позиций, %.2f₽",
                     len(cart), result["total_price"])
        for pid, qty in cart.items():
            p_map = {p.internal_id: p for p in agent.products}
            p = p_map.get(pid)
            name = p.title if p else f"ID:{pid}"
            logger.info("  • %s x%d — %.2f₽", name, qty, (p.price * qty) if p else 0)

        if unavailable_roles:
            logger.warning("⚠️ Недоступные ингредиенты: %s", ", ".join(unavailable_roles))

        # ── Phase 4: Add remaining quantities to basket ──
        logger.info("📤 Phase 4: Добавление товаров в корзину Перекрёстка...")
        add_results = await add_to_basket(cart, available_ids, client)

    # ── Build response ──
    all_details: list[ItemResult] = []
    for pid in cart:
        if pid in available_ids:
            all_details.append(ItemResult(
                internal_id=pid,
                iteration=1,
                status="ok",
                http_status=200,
                message=f"+1 шт (проверка наличия, итого 1/{cart[pid]})",
            ))
    all_details.extend(add_results)

    ok = sum(1 for d in all_details if d.status == "ok")
    fail = sum(1 for d in all_details if d.status == "error")
    total = sum(cart.values())

    logger.info("✅ Готово: %d успешно, %d ошибок из %d запросов", ok, fail, total)

    return BasketResponse(
        success=fail == 0,
        prompt=request.prompt,
        items_from_llm=cart,
        total_requests=total,
        successful=ok,
        failed=fail,
        unavailable_roles=unavailable_roles,
        details=all_details,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
