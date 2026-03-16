#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
  Скрапер каталога Перекрёстка → CSV
  perekrestok-api (async) + camoufox
═══════════════════════════════════════════════════════════════════

Установка:
  pip install perekrestok-api tqdm

Выходные файлы:
  data/products.csv             ← основной CSV для датасета
  data/products.jsonl           ← JSONL (по строке на товар)
  data/categories.json          ← дерево категорий

Использование:
  python scraper.py                           # полный обход
  python scraper.py --max-per-category 50     # быстрый тест
  python scraper.py --resume                  # продолжить
  python scraper.py --search "молоко"         # поиск → CSV
  python scraper.py --list-categories
"""

import json
import csv
import time
import sys
import asyncio
import signal
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from perekrestok_api import PerekrestokAPI
    from perekrestok_api import abstraction
except ImportError:
    print("❌ pip install perekrestok-api")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ═══════════════════════════════════════════════
# Конфиг
# ═══════════════════════════════════════════════

BASE_URL = "https://www.perekrestok.ru/api/customer/1.4.1.0"
SITE_URL = "https://www.perekrestok.ru"
ITEMS_PER_PAGE = 48

# Колонки CSV — именно то что ты просил
CSV_COLUMNS = [
    "internal_id",          # для корзины: PUT .../basket/{id}/plus
    "plu",                  # внешний ID (PLU) для онлайн-запросов
    "title",                # название
    "price",                # текущая цена (руб)
    "old_price",            # старая цена (руб)
    "discount",             # скидка (текст, напр "-12%")
    "image_url",            # ссылка на картинку (x5static, 800x800)
    "category",             # категория
    "category_id",          # ID категории
    "category_path",        # полный путь: "Напитки > Вино"
    "description",          # описание (из feed, если есть)
    "brand",                # бренд
    "weight",               # вес/объём
    "unit",                 # единица (шт, кг, л)
    "in_stock",             # наличие
    "rating",               # рейтинг
    "review_count",         # кол-во отзывов
    "slug",                 # URL-slug
    "product_url",          # ссылка на карточку
    "basket_url",           # API URL для добавления в корзину
    "scraped_at",           # дата сбора
]


# ═══════════════════════════════════════════════
# Парсинг товара из реального API
# ═══════════════════════════════════════════════

def safe_dict(val):
    """Гарантирует dict, даже если пришло число/строка/None."""
    return val if isinstance(val, dict) else {}


def parse_product(item: dict, cat_path: str = "") -> dict:
    """
    Парсит товар из реального ответа API Перекрёстка.
    Структура проверена по debug_feed_raw.json.
    """
    iid = item.get("id", 0)

    # masterData
    md = safe_dict(item.get("masterData"))
    plu = md.get("plu", "")
    slug = md.get("slug", "")
    weight = md.get("weight") or md.get("volume") or ""
    unit_name = md.get("unitName", "")

    # Название
    title = item.get("title", "")

    # Картинка — x5static формат
    img = safe_dict(item.get("image"))
    crop_template = img.get("cropUrlTemplate", "")
    if crop_template:
        # Подставляем размер 800x800-fit
        image_url = crop_template.replace("%s", "800x800-fit")
    else:
        image_url = ""

    # Цена (в копейках → рубли)
    pt = safe_dict(item.get("priceTag"))
    price = (pt.get("price", 0) or 0) / 100
    old_price = (pt.get("grossPrice", 0) or 0) / 100

    # Скидка (текст с лейбла)
    labels = pt.get("labels", []) or []
    discount_text = ""
    for lbl in labels:
        if isinstance(lbl, dict):
            discount_text = lbl.get("text", "")
            if discount_text:
                break

    # Категория
    pcat = safe_dict(item.get("primaryCategory"))
    category = pcat.get("title", "")
    category_id = pcat.get("id", 0)

    # Описание, бренд — из feed (может не быть)
    description = item.get("description", "") or ""
    brand = item.get("brand", "") or ""

    # Наличие
    balance = item.get("balanceState", "")
    in_stock = balance not in ("none", "out", "")

    # Рейтинг
    rating_val = item.get("rating", 0)
    if isinstance(rating_val, dict):
        rating_val = rating_val.get("value", 0) or 0
    review_count = item.get("reviewCount", 0) or 0

    return {
        "internal_id": iid,
        "plu": plu,
        "title": title,
        "price": price,
        "old_price": old_price,
        "discount": discount_text,
        "image_url": image_url,
        "category": category,
        "category_id": category_id,
        "category_path": cat_path or category,
        "description": description,
        "brand": brand,
        "weight": weight,
        "unit": unit_name,
        "in_stock": in_stock,
        "rating": rating_val,
        "review_count": review_count,
        "slug": slug,
        "product_url": f"{SITE_URL}/cat/{slug}" if slug else "",
        "basket_url": f"{BASE_URL}/basket/{iid}/plus",
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ═══════════════════════════════════════════════
# Скрапер
# ═══════════════════════════════════════════════

class Scraper:
    def __init__(self, delay: float = 1.0, output_dir: str = "data"):
        self.delay = delay
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.products_count = 0
        self.errors = []
        self._stop = False
        self.cp_path = self.out / "_checkpoint.json"
        self.scraped_cats: set[int] = set()

    # ─── Категории ───

    async def get_categories(self, api) -> list[dict]:
        print("[1/3] Загружаю категории...")
        resp = await api.Catalog.tree()
        data = resp.json()
        items = data.get("content", {}).get("items", [])

        cats = []
        def walk(lst, pid=None, ptitle=None, depth=0):
            for item in lst:
                c = safe_dict(item.get("category"))
                cats.append({
                    "id": c.get("id", 0), "title": c.get("title", ""),
                    "slug": c.get("slug", ""), "parent_id": pid,
                    "parent_title": ptitle, "depth": depth,
                })
                for ch in item.get("children", []):
                    walk([ch], c.get("id"), c.get("title"), depth + 1)
        walk(items)

        print(f"[OK] {len(cats)} категорий")
        with open(self.out / "categories.json", "w", encoding="utf-8") as f:
            json.dump(cats, f, ensure_ascii=False, indent=2)
        return cats

    # ─── Товары из категории ───

    async def fetch_category(self, api, cat_id: int,
                             max_items: int = 0, cat_path: str = "") -> list[dict]:
        products = []
        page = 1
        while not self._stop:
            filt = abstraction.CatalogFeedFilter()
            filt.CATEGORY_ID = cat_id
            filt.PAGE = page
            filt.PER_PAGE = ITEMS_PER_PAGE
            try:
                resp = await api.Catalog.feed(filter=filt)
                data = resp.json()
            except Exception as e:
                self.errors.append({"cat": cat_id, "page": page, "err": str(e)})
                break

            content = data.get("content", {})
            items = content.get("items", [])
            total = content.get("total", 0)
            if not items:
                break

            for item in items:
                products.append(parse_product(item, cat_path))

            if max_items and len(products) >= max_items:
                return products[:max_items]
            if len(products) >= total:
                break
            page += 1
            await asyncio.sleep(self.delay)
        return products

    # ─── Поиск ───

    async def search(self, api, query: str, pages: int = 1) -> list[dict]:
        products = []
        for page in range(1, pages + 1):
            filt = abstraction.CatalogFeedFilter()
            filt.QUERY = query
            filt.PAGE = page
            filt.PER_PAGE = ITEMS_PER_PAGE
            try:
                resp = await api.Catalog.feed(filter=filt)
                data = resp.json()
            except Exception as e:
                print(f"[ERR] {e}"); break
            items = data.get("content", {}).get("items", [])
            if not items: break
            for item in items:
                products.append(parse_product(item))
            if page < pages:
                await asyncio.sleep(self.delay)
        return products

    # ─── CSV ───

    def save_csv(self, products: list[dict], filename: str = "products.csv"):
        path = self.out / filename
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=";",
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(products)
        print(f"  [CSV] {path} ({len(products)} строк)")

    # ─── Чекпоинт ───

    def _save_cp(self):
        with open(self.cp_path, "w") as f:
            json.dump({"cats": list(self.scraped_cats),
                       "count": self.products_count}, f)

    def _load_cp(self):
        if not self.cp_path.exists(): return
        with open(self.cp_path) as f:
            d = json.load(f)
        self.scraped_cats = set(d.get("cats", []))
        self.products_count = d.get("count", 0)
        print(f"[RESUME] {len(self.scraped_cats)} кат, {self.products_count} товаров")

    # ─── Полный обход ───

    async def scrape_all(self, resume=False, max_per_cat=0):
        start = time.time()

        async with PerekrestokAPI() as api:
            print("\n[TEST] API...")
            try:
                geo = (await api.Geolocation.current()).json()
                city = geo.get("content", {}).get("city", {}).get("name", "?")
                print(f"[TEST] OK — {city}")
            except Exception as e:
                print(f"[ERR] {e}"); return

            cats = await self.get_categories(api)
            if not cats: return

            # Листовые
            pids = {c["parent_id"] for c in cats if c["parent_id"] is not None}
            leaves = [c for c in cats if c["id"] not in pids]
            print(f"\n[2/3] Листовых: {len(leaves)}")

            cmap = {c["id"]: c for c in cats}
            def path(c):
                parts = [c["title"]]
                cur = c
                while cur.get("parent_id") and cur["parent_id"] in cmap:
                    cur = cmap[cur["parent_id"]]
                    parts.insert(0, cur["title"])
                return " > ".join(parts)

            if resume: self._load_cp()

            jl = self.out / "products.jsonl"
            mode = "a" if resume and jl.exists() else "w"
            jf = open(jl, mode, encoding="utf-8")
            seen = set()

            if resume and mode == "a":
                with open(jl, "r", encoding="utf-8") as f:
                    for line in f:
                        try: seen.add(json.loads(line).get("internal_id", 0))
                        except: pass
                print(f"[RESUME] {len(seen)} уже есть")

            try:
                for i, cat in enumerate(leaves):
                    if self._stop: break
                    if resume and cat["id"] in self.scraped_cats: continue

                    cp = path(cat)
                    print(f"\n  [{i+1}/{len(leaves)}] {cp}")

                    prods = await self.fetch_category(api, cat["id"], max_per_cat, cp)
                    new = 0
                    for p in prods:
                        if p["internal_id"] not in seen:
                            seen.add(p["internal_id"])
                            jf.write(json.dumps(p, ensure_ascii=False) + "\n")
                            new += 1
                            self.products_count += 1

                    self.scraped_cats.add(cat["id"])
                    if len(self.scraped_cats) % 10 == 0:
                        self._save_cp(); jf.flush()

                    print(f"    → {len(prods)} товаров ({new} новых) | "
                          f"Всего: {self.products_count}")
                    await asyncio.sleep(self.delay)
            finally:
                jf.close()
                self._save_cp()

        # ── Финал: CSV + JSON ──
        self._finalize(start)

    def _finalize(self, start):
        print(f"\n\n[3/3] Сохраняю...")
        elapsed = time.time() - start

        # Читаем JSONL
        all_p = []
        jl = self.out / "products.jsonl"
        with open(jl, "r", encoding="utf-8") as f:
            for line in f:
                try: all_p.append(json.loads(line))
                except: pass

        # CSV — основной выход
        self.save_csv(all_p)

        # JSON (для программ)
        with open(self.out / "products_full.json", "w", encoding="utf-8") as f:
            json.dump(all_p, f, ensure_ascii=False)

        # Саммари
        with open(self.out / "catalog_summary.json", "w", encoding="utf-8") as f:
            json.dump({
                "scraped_at": datetime.now().isoformat(),
                "elapsed": f"{int(elapsed//3600)}ч {int((elapsed%3600)//60)}м",
                "total_products": len(all_p),
                "categories": len(self.scraped_cats),
                "errors": len(self.errors),
            }, f, ensure_ascii=False, indent=2)

        if self.errors:
            with open(self.out / "errors.json", "w", encoding="utf-8") as f:
                json.dump(self.errors, f, ensure_ascii=False, indent=2)

        if not self._stop and self.cp_path.exists():
            self.cp_path.unlink()

        h, m = int(elapsed // 3600), int((elapsed % 3600) // 60)
        print(f"\n{'═'*60}")
        print(f"  ГОТОВО! {len(all_p)} товаров за {h}ч {m}м")
        print(f"")
        print(f"  📊 CSV:  {self.out}/products.csv")
        print(f"  📋 JSON: {self.out}/products_full.json")
        print(f"  📁 JSONL: {self.out}/products.jsonl")
        print(f"{'═'*60}")
        print(f"\n  📮 Корзина: PUT {BASE_URL}/basket/{{internal_id}}/plus")
        if self._stop:
            print("  [!] Прервано → --resume")


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

async def async_main():
    p = argparse.ArgumentParser(
        description="Скрапер Перекрёстка → CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                              полный обход → CSV
  %(prog)s --max-per-category 50        быстрый тест
  %(prog)s --resume                     продолжить
  %(prog)s --search "молоко" --pages 3  поиск → CSV
  %(prog)s --list-categories
        """)

    p.add_argument("--search", "-s", default=None)
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--list-categories", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--max-per-category", type=int, default=0)
    p.add_argument("--output-dir", default="data")
    args = p.parse_args()

    scraper = Scraper(delay=args.delay, output_dir=args.output_dir)

    if args.list_categories:
        async with PerekrestokAPI() as api:
            cats = await scraper.get_categories(api)
            print(f"\n{'ID':>6}  Категория")
            print("-" * 50)
            for c in cats:
                print(f"{c['id']:>6}  {'  ' * c['depth']}{c['title']}")
        return

    if args.search:
        async with PerekrestokAPI() as api:
            geo = (await api.Geolocation.current()).json()
            city = geo.get("content", {}).get("city", {}).get("name", "?")
            print(f"Город: {city}")
            print(f"Поиск: '{args.search}'\n")

            products = await scraper.search(api, args.search, args.pages)

            # Таблица
            print(f"{'НАЗВАНИЕ':<45} {'ID':>8} {'PLU':>7} {'ЦЕНА':>10} {'СТАРАЯ':>10}")
            print("─" * 85)
            for pr in products:
                print(f"{pr['title'][:43]:<45} {pr['internal_id']:>8} "
                      f"{pr['plu']:>7} {pr['price']:>9.2f}₽ "
                      f"{pr['old_price']:>9.2f}₽" if pr['old_price'] else "")

            print(f"\nИтого: {len(products)}")

            if products:
                scraper.save_csv(products, "search_results.csv")
                print(f"\n  📊 {scraper.out}/search_results.csv")
        return

    # Полный обход
    print("═" * 60)
    print("  ПЕРЕКРЁСТОК → CSV")
    print(f"  Задержка: {args.delay}с")
    if args.max_per_category:
        print(f"  Лимит: {args.max_per_category}/категория")
    print("═" * 60)

    await scraper.scrape_all(resume=args.resume, max_per_cat=args.max_per_category)


def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()