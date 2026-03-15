"""Product retrieval: BM25 full-text search with ranking by rating/reviews/discount."""

import math
import re

from .models import Product


# ── Tokenization ──

def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if len(w) > 1]


# ── BM25 ──

class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[list[str]] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0
        self.df: dict[str, int] = {}
        self.n_docs: int = 0

    def fit(self, documents: list[str]):
        self.docs = [_tokenize(doc) for doc in documents]
        self.n_docs = len(self.docs)
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = sum(self.doc_len) / max(self.n_docs, 1)

        self.df = {}
        for doc in self.docs:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1

    def score(self, query: str) -> list[float]:
        query_terms = _tokenize(query)
        scores = [0.0] * self.n_docs

        for term in query_terms:
            if term not in self.df:
                continue
            idf = math.log((self.n_docs - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1)

            for i, doc in enumerate(self.docs):
                tf = doc.count(term)
                if tf == 0:
                    continue
                dl = self.doc_len[i]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * numerator / denominator

        return scores


# ── Product index ──

_bm25: BM25 | None = None
_indexed_products: list[Product] = []


def _product_text(p: Product) -> str:
    return f"{p.category} {p.title} {p.slug}"


def _quality_score(p: Product) -> float:
    """Score based on rating, reviews, discount, and price."""
    score = 0.0

    # Rating: 0-500 scale
    if p.rating > 0:
        score += (p.rating / 500) * 2.0

    # Reviews: log scale bonus
    if p.review_count > 0:
        score += math.log1p(p.review_count) * 0.3

    # Discount bonus
    if p.discount:
        try:
            pct = abs(float(p.discount.replace("%", "").replace(",", ".")))
            score += pct * 0.02
        except ValueError:
            pass

    return score


def _build_index(products: list[Product]):
    global _bm25, _indexed_products
    _indexed_products = products
    _bm25 = BM25()
    _bm25.fit([_product_text(p) for p in products])


def retrieve_products(
    query: str,
    products: list[Product],
    top_k: int = 20,
) -> list[Product]:
    """BM25 search with quality-based reranking."""
    global _bm25, _indexed_products
    if _bm25 is None or _indexed_products is not products:
        _build_index(products)

    bm25_scores = _bm25.score(query)

    combined = []
    for idx, bm25_sc in enumerate(bm25_scores):
        if bm25_sc > 0:
            p = _indexed_products[idx]
            quality = _quality_score(p)
            final_score = bm25_sc + quality * 0.5
            combined.append((idx, final_score))

    combined.sort(key=lambda x: x[1], reverse=True)

    results = [_indexed_products[idx] for idx, _ in combined[:top_k]]

    if len(results) < 3:
        fallback = sorted(products, key=lambda p: (p.rating, p.review_count), reverse=True)
        return fallback[:top_k]

    return results


def rank_available(
    candidate_ids: list[int],
    available_ids: set[int],
    product_map: dict[int, Product],
) -> int | None:
    """Pick the best available candidate from a list, ranked by quality.

    Args:
        candidate_ids: ordered list of candidate internal_ids
        available_ids: set of internal_ids confirmed available by server
        product_map: {internal_id: Product}

    Returns:
        Best available internal_id, or None if all unavailable.
    """
    available_candidates = [
        pid for pid in candidate_ids
        if pid in available_ids and pid in product_map
    ]

    if not available_candidates:
        return None

    # Rank by quality: rating > review_count > discount > lower price
    return max(
        available_candidates,
        key=lambda pid: (
            _quality_score(product_map[pid]),
            -product_map[pid].price,
        ),
    )
