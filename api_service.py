"""
═══════════════════════════════════════════════════════════════════
  OmniBuyAI API Service — Backend для Chrome Extension
═══════════════════════════════════════════════════════════════════

Endpoints:
  POST /api/v1/chat       — Отправить сообщение AI, получить ответ
  POST /api/v1/search     — Поиск товаров по запросу
  GET  /api/v1/products   — Получить все товары
  POST /api/v1/cart/add   — Добавить товар в корзину Перекрёстка
  POST /api/v1/cart/remove— Удалить товар из корзины
  GET  /api/v1/cart       — Получить содержимое корзины
  GET  /api/v1/health     — Проверка доступности
  POST /api/v1/basket/build — Построить корзину по промту (полный цикл)

Usage:
  uv run uvicorn api_service:app --reload --port 8000
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from omnibuyai import GroceryAgent
from omnibuyai.data_loader import load_products

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════

BASKET_URL = "https://www.perekrestok.ru/api/customer/1.4.1.0/basket/{id}/plus"
DELAY_BETWEEN_REQUESTS = 0.3

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

# ═══════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════

class UserSession(BaseModel):
    auth_token: str = Field(..., description="Auth token: 'Bearer eyJ...'")
    cookies: dict[str, str] = Field(..., description="Browser cookies")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Сообщение пользователя")
    products: list[dict] = Field(default=[], description="Товары с текущей страницы")
    context: dict = Field(default={}, description="Дополнительный контекст")


class ChatResponse(BaseModel):
    type: str = Field(..., description="Тип ответа: text, products, confirmation, cart_action")
    text: str = Field(default="", description="Текстовое сообщение")
    products: list[dict] = Field(default=[], description="Список товаров")
    action: Optional[str] = None
    productName: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Поисковый запрос")
    filters: dict = Field(default={}, description="Фильтры")


class SearchResponse(BaseModel):
    success: bool
    products: list[dict]
    total: int


class ProductResponse(BaseModel):
    success: bool
    products: list[dict]
    total: int


class CartAddRequest(BaseModel):
    product_id: int = Field(..., description="ID товара")
    quantity: int = Field(default=1, description="Количество")


class CartRemoveRequest(BaseModel):
    product_id: int = Field(..., description="ID товара")


class CartResponse(BaseModel):
    success: bool
    items: list[dict]
    total: float


class BasketBuildRequest(BaseModel):
    prompt: str = Field(..., description="Промт пользователя")
    session: UserSession


class BasketBuildResponse(BaseModel):
    success: bool
    prompt: str
    items: dict[int, int]
    total_requests: int
    successful: int
    failed: int
    unavailable_roles: list[str] = []
    details: list[dict]


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# ═══════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════

def get_product_info(internal_id: int) -> Optional[dict]:
    """Get product info from CSV by internal_id."""
    try:
        products = load_products()
        for p in products:
            if p.internal_id == internal_id:
                return {
                    "id": p.internal_id,
                    "name": p.title,
                    "price": p.price,
                    "image": p.image_url or "",
                    "category": p.category or "",
                }
        return None
    except Exception as e:
        logger.error("Error getting product %d: %s", internal_id, e)
        return None


async def check_availability_perekrestok(
    candidate_ids: list[int],
    client: httpx.AsyncClient,
) -> set[int]:
    """Check which products are available by trying to add 1 unit via PUT."""
    logger.info("🔍 Проверка наличия %d кандидатов...", len(candidate_ids))
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
) -> list[dict]:
    """Add final cart items."""
    results = []
    logger.info("🛒 Добавление %d позиций в корзину...", len(cart))

    for internal_id, quantity in cart.items():
        remaining = quantity - 1 if internal_id in already_added else quantity

        for i in range(remaining):
            url = BASKET_URL.format(id=internal_id)
            iteration = i + 2 if internal_id in already_added else i + 1

            try:
                resp = await client.put(url)

                if resp.status_code in (200, 201, 204):
                    results.append({
                        "internal_id": internal_id,
                        "iteration": iteration,
                        "status": "ok",
                        "http_status": resp.status_code,
                        "message": f"+1 шт (итого {iteration}/{quantity})",
                    })
                elif resp.status_code == 401:
                    results.append({
                        "internal_id": internal_id,
                        "iteration": iteration,
                        "status": "error",
                        "http_status": 401,
                        "message": "Токен истёк — перелогиньтесь на perekrestok.ru",
                    })
                    logger.error("🔒 Токен истёк, прерываем")
                    return results
                else:
                    body = resp.text[:200] if resp.text else ""
                    results.append({
                        "internal_id": internal_id,
                        "iteration": iteration,
                        "status": "error",
                        "http_status": resp.status_code,
                        "message": body,
                    })
            except Exception as e:
                results.append({
                    "internal_id": internal_id,
                    "iteration": iteration,
                    "status": "error",
                    "message": str(e),
                })

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    return results


# ═══════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════

app = FastAPI(
    title="OmniBuyAI API",
    description="API для Chrome Extension — AI помощник для Перекрёстка",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для extension можно оставить *
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════

@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    """Проверка доступности сервиса."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
    )


@app.get("/api/v1/products", response_model=ProductResponse)
async def get_products():
    """Получить все товары из CSV."""
    try:
        products = load_products()
        product_list = [
            {
                "id": p.internal_id,
                "name": p.title,
                "price": p.price,
                "image": p.image_url or "",
                "category": p.category or "",
                "rating": p.rating or 0,
            }
            for p in products
        ]
        return ProductResponse(
            success=True,
            products=product_list,
            total=len(product_list),
        )
    except Exception as e:
        logger.error("Error loading products: %s", e)
        raise HTTPException(500, f"Error loading products: {e}")


@app.post("/api/v1/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """Поиск товаров по названию."""
    try:
        products = load_products()
        query_lower = request.query.lower()

        # Simple search by title
        matched = [
            {
                "id": p.internal_id,
                "name": p.title,
                "price": p.price,
                "image": p.image_url or "",
                "category": p.category or "",
            }
            for p in products
            if query_lower in p.title.lower()
        ]

        return SearchResponse(
            success=True,
            products=matched[:50],  # Limit to 50 results
            total=len(matched),
        )
    except Exception as e:
        logger.error("Error searching products: %s", e)
        raise HTTPException(500, f"Error searching: {e}")


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Обработка сообщения пользователя.
    Интегрируется с GroceryAgent для AI-ответов.
    """
    try:
        logger.info("💬 Chat request: %s", request.message)

        agent = GroceryAgent()

        # Try to analyze the message
        result = agent.clarify(request.message)

        if result.get("status") == "need_info":
            # Need more information
            return ChatResponse(
                type="text",
                text=result.get("question", "Уточните ваш запрос"),
            )

        # Ready to build cart
        params = result["params"]
        logger.info("✅ Параметры: %s", params)

        # Get candidates
        partial, groups = agent.get_all_candidate_ids(params)

        # Get product info for display
        product_map = {p.internal_id: p for p in agent.products}
        products_to_show = []

        for group in groups[:5]:  # Show first 5 groups
            for candidate_id in group["candidates"][:2]:  # 2 candidates per group
                p = product_map.get(candidate_id)
                if p:
                    products_to_show.append({
                        "id": p.internal_id,
                        "name": p.title,
                        "price": p.price,
                        "image": p.image_url or "",
                        "category": p.category or "",
                    })

        if products_to_show:
            return ChatResponse(
                type="products",
                text=f"Нашёл товары для вашего запроса. Выберите что добавить:",
                products=products_to_show,
            )
        else:
            return ChatResponse(
                type="text",
                text="К сожалению, не нашёл подходящих товаров. Попробуйте другой запрос.",
            )

    except Exception as e:
        logger.error("Error in chat: %s", e)
        # Fallback response
        return ChatResponse(
            type="text",
            text=f"Произошла ошибка: {str(e)}. Попробуйте ещё раз.",
        )


@app.post("/api/v1/cart/add")
async def add_to_cart(request: CartAddRequest, session: UserSession = None):
    """Добавить товар в корзину Перекрёстка."""
    try:
        logger.info("🛒 Add to cart: ID=%d, qty=%d", request.product_id, request.quantity)

        # Get product info
        product = get_product_info(request.product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        # If session provided, add via API
        if session:
            token = session.auth_token.strip()
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"

            headers = {**HEADERS, "auth": token}

            async with httpx.AsyncClient(
                headers=headers,
                cookies=session.cookies,
                timeout=15.0,
            ) as client:
                url = BASKET_URL.format(id=request.product_id)
                resp = await client.put(url)

                if resp.status_code in (200, 201, 204):
                    return {
                        "success": True,
                        "message": f"Добавлено: {product['name']}",
                        "product": product,
                    }
                elif resp.status_code == 401:
                    return {
                        "success": False,
                        "error": "Токен истёк — перелогиньтесь на perekrestok.ru",
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status_code}: {resp.text[:100]}",
                    }
        else:
            # No session - return product info for frontend to handle
            return {
                "success": True,
                "message": f"Товар готов к добавлению: {product['name']}",
                "product": product,
                "requires_session": True,
            }

    except Exception as e:
        logger.error("Error adding to cart: %s", e)
        return {"success": False, "error": str(e)}


@app.post("/api/v1/cart/remove")
async def remove_from_cart(request: CartRemoveRequest, session: UserSession = None):
    """Удалить товар из корзины Перекрёстка."""
    try:
        logger.info("🗑️ Remove from cart: ID=%d", request.product_id)

        if not session:
            return {"success": False, "error": "Session required"}

        token = session.auth_token.strip()
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"

        headers = {**HEADERS, "auth": token}

        # Note: Perekrestok API may not have remove endpoint, this is a placeholder
        async with httpx.AsyncClient(
            headers=headers,
            cookies=session.cookies,
            timeout=15.0,
        ) as client:
            # Try to remove (implementation depends on actual API)
            url = BASKET_URL.format(id=request.product_id)
            resp = await client.delete(url)

            if resp.status_code in (200, 201, 204):
                return {"success": True, "message": "Удалено из корзины"}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:100]}",
                }

    except Exception as e:
        logger.error("Error removing from cart: %s", e)
        return {"success": False, "error": str(e)}


@app.get("/api/v1/cart")
async def get_cart(session: UserSession = None):
    """Получить содержимое корзины Перекрёстка."""
    try:
        if not session:
            return {"success": False, "error": "Session required"}

        token = session.auth_token.strip()
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"

        headers = {**HEADERS, "auth": token}

        # Note: Implementation depends on actual Perekrestok API
        # This is a placeholder
        return {
            "success": True,
            "items": [],
            "total": 0,
            "message": "Get cart not fully implemented",
        }

    except Exception as e:
        logger.error("Error getting cart: %s", e)
        return {"success": False, "error": str(e)}


@app.post("/api/v1/basket/build", response_model=BasketBuildResponse)
async def build_basket(request: BasketBuildRequest):
    """
    Построить корзину по промту (полный цикл).
    LLM → проверка наличия → добавление в корзину.
    """
    logger.info("=" * 60)
    logger.info("📝 Build basket: %s", request.prompt)
    logger.info("=" * 60)

    token = request.session.auth_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    headers = {**HEADERS, "auth": token}
    cookies = request.session.cookies

    agent = GroceryAgent()

    try:
        # Phase 1: LLM analysis
        logger.info("🧠 Phase 1: Анализ запроса...")
        clarify_result = agent.clarify(request.prompt)

        if clarify_result.get("status") == "need_info":
            question = clarify_result.get("question", "Недостаточно информации")
            logger.warning("❓ LLM запрашивает уточнение: %s", question)
            raise HTTPException(422, f"Уточните запрос: {question}")

        params = clarify_result["params"]
        logger.info("✅ Параметры: дней=%s, людей=%s, предпочтения=%s",
                    params.get("days"), params.get("people"), params.get("preferences"))

        # Phase 2: Get candidates
        logger.info("📋 Phase 2: Генерация кандидатов...")
        partial_result, candidate_groups = agent.get_all_candidate_ids(params)

        all_candidate_ids = partial_result["all_candidate_ids"]
        meal_plan = partial_result["meal_plan"]

        logger.info("📦 LLM выбрал %d уникальных кандидатов", len(all_candidate_ids))

        # Phase 3: Check availability
        logger.info("🔍 Phase 3: Проверка наличия...")
        async with httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            timeout=15.0,
        ) as client:
            available_ids = await check_availability_perekrestok(all_candidate_ids, client)

            # Phase 4: Build cart
            logger.info("⚖️ Phase 4: Выбор лучших товаров...")
            result = agent.finalize_cart(candidate_groups, available_ids, meal_plan, params)

            cart = result.get("cart", {})
            unavailable_roles = result.get("unavailable", [])

            if not cart:
                logger.error("🚫 Корзина пуста")
                raise HTTPException(422, "Все товары недоступны. Попробуйте другой запрос.")

            logger.info("🛒 Финальная корзина: %d позиций", len(cart))

            # Phase 5: Add to basket
            logger.info("📤 Phase 5: Добавление в корзину...")
            add_results = await add_to_basket(cart, available_ids, client)

        # Build response
        all_details = []
        for pid in cart:
            if pid in available_ids:
                all_details.append({
                    "internal_id": pid,
                    "iteration": 1,
                    "status": "ok",
                    "http_status": 200,
                    "message": f"+1 шт (проверка наличия)",
                })
        all_details.extend(add_results)

        ok = sum(1 for d in all_details if d.get("status") == "ok")
        fail = sum(1 for d in all_details if d.get("status") == "error")
        total = sum(cart.values())

        logger.info("✅ Готово: %d успешно, %d ошибок", ok, fail)

        return BasketBuildResponse(
            success=fail == 0,
            prompt=request.prompt,
            items=cart,
            total_requests=total,
            successful=ok,
            failed=fail,
            unavailable_roles=unavailable_roles,
            details=all_details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error building basket: %s", e)
        raise HTTPException(500, f"Error: {str(e)}")


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
