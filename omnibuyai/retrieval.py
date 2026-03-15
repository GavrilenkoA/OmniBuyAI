import os

import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

from .config import OPENAI_API_KEY, EMBEDDING_MODEL, DATA_DIR
from .models import Product


_client = OpenAI(api_key=OPENAI_API_KEY)
EMBEDDINGS_PATH = os.path.join(DATA_DIR, "embeddings.npy")
IDS_PATH = os.path.join(DATA_DIR, "embedding_ids.npy")


def _product_text(p: Product) -> str:
    return f"{p.category}: {p.name}. {p.description}"


def _get_embeddings(texts: list[str]) -> np.ndarray:
    response = _client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return np.array([e.embedding for e in response.data])


def build_embeddings(products: list[Product]) -> None:
    texts = [_product_text(p) for p in products]
    embeddings = _get_embeddings(texts)
    ids = np.array([p.id for p in products])
    np.save(EMBEDDINGS_PATH, embeddings)
    np.save(IDS_PATH, ids)


def retrieve_products(
    query: str,
    products: list[Product],
    top_k: int = 20,
) -> list[Product]:
    if not os.path.exists(EMBEDDINGS_PATH):
        build_embeddings(products)

    embeddings = np.load(EMBEDDINGS_PATH)
    ids = np.load(IDS_PATH)

    query_emb = _get_embeddings([query])
    similarities = cosine_similarity(query_emb, embeddings)[0]

    top_indices = np.argsort(similarities)[-top_k:][::-1]
    top_ids = set(ids[top_indices].tolist())

    product_map = {p.id: p for p in products}
    return [product_map[pid] for pid in ids[top_indices] if pid in product_map]
