import os

import pandas as pd

from .config import DATA_DIR
from .models import Product


def load_products() -> list[Product]:
    path = os.path.join(DATA_DIR, "products.csv")
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")

    df = df.fillna({"old_price": 0, "discount": "", "rating": 0, "review_count": 0,
                     "slug": "", "description": "", "weight": "", "unit": "",
                     "image_url": "", "brand": "", "category": ""})

    products = []
    for _, row in df.iterrows():
        products.append(
            Product(
                internal_id=int(row["internal_id"]),
                title=str(row["title"]),
                price=float(row["price"]),
                old_price=float(row.get("old_price", 0)),
                discount=str(row.get("discount", "")),
                category=str(row["category"]),
                rating=float(row.get("rating", 0)),
                review_count=int(row.get("review_count", 0)),
                slug=str(row.get("slug", "")),
                description=str(row.get("description", "")),
                weight=str(row.get("weight", "")),
                unit=str(row.get("unit", "")),
                image_url=str(row.get("image_url", "")),
                brand=str(row.get("brand", "")),
            )
        )

    return products
