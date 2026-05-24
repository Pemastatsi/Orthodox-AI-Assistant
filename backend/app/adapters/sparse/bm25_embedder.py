"""BM25 sparse-vector embedder for the ingestion pipeline (D-RET-001, ADR-0011).

Computed at upsert time so T-003 can enable hybrid retrieval without re-ingestion. The model
downloads its weights on first use; the worker constructs one instance per process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.adapters.vector_store.base import SparseVector

if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding


_MODEL_NAME = "Qdrant/bm25"


class Bm25SparseEmbedder:
    def __init__(self, *, model_name: str = _MODEL_NAME, model: Any = None) -> None:
        self._model_name = model_name
        self._model = model

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        from fastembed import SparseTextEmbedding

        self._model = SparseTextEmbedding(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[SparseVector]:
        if not texts:
            return []
        model: SparseTextEmbedding = self._ensure_model()  # type: ignore[assignment]
        out: list[SparseVector] = []
        for emb in model.embed(texts):
            out.append(
                SparseVector(
                    indices=[int(i) for i in emb.indices.tolist()],
                    values=[float(v) for v in emb.values.tolist()],
                )
            )
        return out


__all__ = ["Bm25SparseEmbedder"]
