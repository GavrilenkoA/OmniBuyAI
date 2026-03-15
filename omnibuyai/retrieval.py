"""Product retrieval: BM25 full-text search + optional semantic reranking."""

import math
import re
from collections import Counter

import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

from .config import OPENAI_API_KEY, EMBEDDING_MODEL
from .models import Product

_client = OpenAI(api_key=OPENAI_API_KEY)


# ── Tokenization ──

def _tokenize(text: str) -> list[str]:
    """Lowercase + split into words, strip punctuation."""
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
    return f"{p.category} {p.name} {p.description}"


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
    """BM25 full-text search over products."""
    global _bm25, _indexed_products
    if _bm25 is None or _indexed_products is not products:
        _build_index(products)

    scores = _bm25.score(query)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, sc in ranked:
        if sc > 0 and len(results) < top_k:
            results.append(_indexed_products[idx])

    # If BM25 found very little, return all products as fallback
    if len(results) < 3:
        return products[:top_k]

    return results


def semantic_rerank(
    query: str,
    candidates: list[Product],
    top_k: int = 5,
) -> list[Product]:
    """Rerank candidates using OpenAI embeddings. Use when choosing between similar products."""
    if len(candidates) <= top_k:
        return candidates

    texts = [_product_text(p) for p in candidates]
    response = _client.embeddings.create(input=[query] + texts, model=EMBEDDING_MODEL)
    embeddings = np.array([e.embedding for e in response.data])

    query_emb = embeddings[0:1]
    doc_embs = embeddings[1:]

    similarities = cosine_similarity(query_emb, doc_embs)[0]
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    return [candidates[i] for i in top_indices]
