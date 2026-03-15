import asyncio
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from omnibuyai import GroceryAgent

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

DELAY_BETWEEN_REQUESTS = 0.3  # секунд

agent = GroceryAgent()

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
    """Входной запрос: промт + сессия."""
    prompt: str = Field(
        ...,
        description="Промт пользователя",
    )
    session: UserSession

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt": "Собери мне ужин на двоих примерно за 5000 рублей",
                    "session": {
                        "auth_token": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzUxMiJ9.eyJqdGkiOiIwMmE2Njg1NC1hYmU2LTQ4ZDItYWM2MC1lOTAzNDk0ODc5MzkiLCJpYXQiOjE3NzM1NjMyOTMsImV4cCI6MTc3MzU5MjA5MywiZCI6IjcyN2MxMTJhLWJhNzYtNGFiYy04ODdkLTJiZTI0ODBiNTc3MyIsImFwaSI6IjEuNC4xLjAiLCJpcCI6IjIxMi4xMTMuMTA5LjkwIiwidSI6IjkyYjI5MjI4LTQyNmYtNDJmYy05YThhLTY5NWU4MjhkNDgxNSIsInQiOjF9.AKhuudP-omJdFmLfifpXlInNNMMggh-HvWjPGog1WPT_ApBz4GN3hWl24qV7mjkIJWqN8wji6cnO7A5ihTFgnE4SAS_Oa0be1mKrr6utqFDo3KLtVL3zCD8CbtlxjETgJ69QNCmI-4GNnv7uwVFM4InKMBOeaQM-cQ6tx3GIK1dYjkh8",
                        "cookies": {
                            "agreements": "j:{\"isAdultContentEnabled\":false,\"isAppAppInstallPromptClosed\":true}",
                            "spid": "1773563064421_3eab3bf97c3b2db5d6cf609bbc28dbe0_63mrgmmeb58nucxp",
                            "session": "%7B%22accessToken%22%3A%22eyJ0eXAi...%22%7D",
                            "_ym_uid": "1773560204196730617",
                            "_ym_d": "1773563295",
                            "encryptedSessionId": "a4518e9ac979a1f4af30396c3323cff55dd4fd9657a4206846c57adfb6c87714",
                            "server_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0b2tlbi...",
                            "session_token_timestamp": "1773649786263",
                            "spjs": "1773572619228_48d6a19f_013525d7_...",
                            "spsc": "1773572619228_fd58cb36086ff3d0..."
                        }
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
    details: list[ItemResult]


# ═══════════════════════════════════════════════
# FastAPI
# ═══════════════════════════════════════════════

app = FastAPI(
    title="Perekrestok Basket Service",
    description=(
        "Промт → LLM → корзина Перекрёстка.\n\n"
        "Пользователь передаёт промт и свои auth данные, "
        "сервис собирает корзину через AI и добавляет товары."
    ),
    version="1.0.0",
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
    description=(
        "1. Промт уходит в LLM модуль\n"
        "2. LLM возвращает {internal_id: quantity}\n"
        "3. Сервис делает PUT запросы в корзину\n"
        "4. Возвращает результат"
    ),
)
async def build_basket(request: PromptRequest):

    # ── Шаг 1: LLM ──
    try:
        items = agent.run(request.prompt).get("cart")
    except Exception as e:
        raise HTTPException(500, f"Ошибка LLM модуля: {e}")

    if not items:
        raise HTTPException(
            422, "LLM не вернул товаров для этого промта. Попробуйте другой запрос."
        )

    # ── Шаг 2: добавляем в корзину ──
    token = request.session.auth_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    headers = {**HEADERS, "auth": token}
    cookies = request.session.cookies

    results: list[ItemResult] = []
    total = sum(items.values())
    ok = 0
    fail = 0

    async with httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        timeout=15.0,
    ) as client:

        for internal_id, quantity in items.items():
            for i in range(quantity):
                url = BASKET_URL.format(id=internal_id)

                try:
                    resp = await client.put(url)

                    if resp.status_code in (200, 201, 204):
                        ok += 1
                        results.append(ItemResult(
                            internal_id=internal_id,
                            iteration=i + 1,
                            status="ok",
                            http_status=resp.status_code,
                            message=f"+1 шт (итого {i+1}/{quantity})",
                        ))
                    elif resp.status_code == 401:
                        fail += 1
                        results.append(ItemResult(
                            internal_id=internal_id,
                            iteration=i + 1,
                            status="error",
                            http_status=401,
                            message="Токен истёк — перелогиньтесь на perekrestok.ru",
                        ))
                        # Нет смысла продолжать
                        return BasketResponse(
                            success=False,
                            prompt=request.prompt,
                            items_from_llm=items,
                            total_requests=ok + fail,
                            successful=ok,
                            failed=fail,
                            details=results,
                        )
                    else:
                        fail += 1
                        body = resp.text[:200] if resp.text else ""
                        results.append(ItemResult(
                            internal_id=internal_id,
                            iteration=i + 1,
                            status="error",
                            http_status=resp.status_code,
                            message=body,
                        ))

                except Exception as e:
                    fail += 1
                    results.append(ItemResult(
                        internal_id=internal_id,
                        iteration=i + 1,
                        status="error",
                        message=str(e),
                    ))

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    return BasketResponse(
        success=fail == 0,
        prompt=request.prompt,
        items_from_llm=items,
        total_requests=total,
        successful=ok,
        failed=fail,
        details=results,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}