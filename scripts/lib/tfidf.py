"""Minimal stemmed TF-IDF over skill descriptions. No external dependencies."""
from __future__ import annotations

import math
import re
from collections import Counter

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with",
    "when", "is", "are", "this", "that", "it", "its", "as", "by", "be",
    "not", "use", "using", "your", "you", "if", "into", "from", "at",
}
_SUFFIXES = ("ational", "izer", "ation", "iciti", "ative", "ing", "edly",
             "ed", "es", "ly", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) - len(suffix) > 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9_/-]*", text.lower())
    return [_stem(w) for w in words if w not in _STOPWORDS and len(w) > 1]


class TfidfIndex:
    def __init__(self, documents: dict[str, str]):
        self.doc_ids = list(documents.keys())
        self.tokens = {doc_id: tokenize(text) for doc_id, text in documents.items()}
        self.vocab = sorted({tok for toks in self.tokens.values() for tok in toks})
        self.idf = self._compute_idf()
        self.vectors = {doc_id: self._vectorize(toks) for doc_id, toks in self.tokens.items()}

    def _compute_idf(self) -> dict[str, float]:
        n = len(self.doc_ids)
        df = Counter()
        for toks in self.tokens.values():
            for tok in set(toks):
                df[tok] += 1
        return {tok: math.log((1 + n) / (1 + df[tok])) + 1 for tok in self.vocab}

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        vec = {tok: (count / total) * self.idf.get(tok, 0.0) for tok, count in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {tok: v / norm for tok, v in vec.items()}

    def vectorize_query(self, text: str) -> dict[str, float]:
        return self._vectorize(tokenize(text))

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        keys = set(a) & set(b)
        return sum(a[k] * b[k] for k in keys)

    def rank(self, query_vec: dict[str, float]) -> list[tuple[str, float]]:
        scored = [(doc_id, self.cosine(query_vec, vec)) for doc_id, vec in self.vectors.items()]
        return sorted(scored, key=lambda pair: pair[1], reverse=True)

    def pairwise_similarities(self) -> list[tuple[str, str, float]]:
        pairs = []
        for i, a in enumerate(self.doc_ids):
            for b in self.doc_ids[i + 1:]:
                pairs.append((a, b, self.cosine(self.vectors[a], self.vectors[b])))
        return pairs
