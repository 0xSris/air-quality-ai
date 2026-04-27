from __future__ import annotations

import math
from functools import cached_property


class EmbeddingService:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self):
        try:
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer(self.model_name)
        except Exception:
            return None

    def similarity_scores(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        if self._model is not None:
            try:
                embeddings = self._model.encode([query, *documents], normalize_embeddings=True)
                query_embedding = embeddings[0]
                return [float(query_embedding @ doc_embedding) for doc_embedding in embeddings[1:]]
            except Exception:
                pass
        return [self._fallback_similarity(query, document) for document in documents]

    @staticmethod
    def _fallback_similarity(query: str, document: str) -> float:
        query_terms = query.lower().split()
        document_terms = document.lower().split()
        if not query_terms or not document_terms:
            return 0.0
        overlap = len(set(query_terms) & set(document_terms))
        norm = math.sqrt(len(set(query_terms))) * math.sqrt(len(set(document_terms)))
        return overlap / norm if norm else 0.0
