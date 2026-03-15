import json
import os

import pandas as pd

from .config import DATA_DIR
from .models import Product


def load_products() -> list[Product]:
    info_path = os.path.join(DATA_DIR, "info_product.csv")
    cal_path = os.path.join(DATA_DIR, "calories.csv")
    desc_path = os.path.join(DATA_DIR, "description.json")

    info_df = pd.read_csv(info_path)
    cal_df = pd.read_csv(cal_path)

    merged = info_df.merge(cal_df, on="id", how="left")
    merged = merged.fillna(0)

    with open(desc_path, "r", encoding="utf-8") as f:
        descriptions = json.load(f)

    desc_map = {item["id"]: item for item in descriptions}

    products = []
    for _, row in merged.iterrows():
        desc_info = desc_map.get(int(row["id"]), {})
        products.append(
            Product(
                id=int(row["id"]),
                category=str(row["category"]),
                name=str(row["name"]),
                price=float(row["price"]),
                calories=float(row.get("calories", 0)),
                proteins=float(row.get("proteins", 0)),
                fats=float(row.get("fats", 0)),
                carbs=float(row.get("carbs", 0)),
                description=desc_info.get("description", ""),
                compound=desc_info.get("compound", ""),
            )
        )

    return products
