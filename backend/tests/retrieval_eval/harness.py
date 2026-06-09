"""Retrieval-eval harness: load a gold set, run A3 (the real `Retriever`) per case, and collect
the ranked chunk IDs that `metrics.py` then scores.

The harness is **route-agnostic by construction**: the same `RetrievalHarness` runs against either
(a) an offline, deterministic stand-in (the `LexicalEmbeddingProvider` + `InMemoryVectorStore`
built here) for free CI smoke runs, or (b) a real embedding `ModelRoute` + Qdrant for the
founder-gated certification run. Only the injected `Retriever` differs.

Offline embedding rationale: the project's `FakeEmbeddingProvider` hashes the *whole* text, so its
vectors are semantically meaningless and retrieval would be random. `LexicalEmbeddingProvider`
instead hashes per token (bag-of-words), so cosine similarity tracks shared vocabulary — enough for
a lexically-distinct gold set to retrieve its target chunk deterministically, with zero API cost.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.adapters.vector_store.base import (
    ScoredChunk as AdapterScoredChunk,
)
from app.adapters.vector_store.base import (
    SparseVector,
    VectorFilter,
)
from app.core.auth import make_dev_principal
from app.domain.models._base import WireModel
from app.domain.models.chunk import Chunk
from app.domain.models.principal import Principal
from app.domain.models.retrieval_plan import (
    RetrievalConfig,
    RetrievalFilters,
    RetrievalPlan,
    RetrievalRerankerConfig,
)
from app.domain.services.retriever import Retriever

from tests.fixtures.fakes import FakeEmbeddingProvider
from tests.retrieval_eval.metrics import CaseResult

_REPO_ROOT = Path(__file__).resolve().parents[3]
TINY_APPROVED_CORPUS = (
    _REPO_ROOT / "tests" / "fixtures" / "corpus" / "tiny_approved_corpus.json"
)

ConfigLabel = Literal["dense_only", "hybrid", "hybrid_rerank"]

# Retrieval ranking is independent of the answer mode (A3 uses semantic_query, k, filters, and the
# retrieval config — not answer_mode). The gold set's `answerMode` now shares the single AnswerMode
# taxonomy (answer-mode.schema.json == RetrievalPlan.answer_mode, enforced by
# scripts/verify_openapi_enums.py), so any gold value is a legal plan value; we still pin one fixed
# value here because the plan's answer_mode has no effect on retrieval metrics.
_PLAN_ANSWER_MODE = "consensus"


# --------------------------------------------------------------------------------------------
# Gold-set models (docs/schemas/retrieval-eval-gold-set.schema.json)
# --------------------------------------------------------------------------------------------
class GoldCase(WireModel):
    id: str
    query: str
    language: Literal["en", "el", "grc"]
    expected_chunk_ids: list[str]
    minimally_sufficient_chunk_ids: list[str]
    answer_mode: Literal[
        "consensus",
        "institutional_policy",
        "scholarly_dispute",
        "pastoral_guidance",
        "insufficient",
    ]
    sensitivity_primary: Literal[
        "normal",
        "pastoral_advice",
        "political",
        "medical",
        "comparative_religion",
        "canonical_dispute",
        "other_sensitive",
    ]
    notes: str


class GoldSet(WireModel):
    tenant_id: str
    version: str
    created_by: str
    reviewed_by: list[str]
    corpus_version_at_curation: str
    cases: list[GoldCase]


def load_gold_set(path: Path) -> GoldSet:
    """Load and validate a gold-set JSON file (drops the optional ``$schema`` instance hint)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("$schema", None)
    return GoldSet.model_validate(data)


# --------------------------------------------------------------------------------------------
# Offline, deterministic retrieval stand-ins
# --------------------------------------------------------------------------------------------
def _token_bucket(token: str, dim: int) -> int:
    # Stable across processes (unlike Python's salted hash()).
    digest = hashlib.md5(token.encode("utf-8")).digest()  # noqa: S324 - not security
    return int.from_bytes(digest[:4], "big") % dim


def lexical_embed(text: str, dim: int) -> list[float]:
    """L2-normalized bag-of-words hashing vector; cosine ≈ shared-vocabulary overlap."""
    vec = [0.0] * dim
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        vec[_token_bucket(token, dim)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


class LexicalEmbeddingProvider(FakeEmbeddingProvider):
    """`FakeEmbeddingProvider` with token-level (not whole-text) hashing, so ranking is meaningful.

    Inherits the provider property surface (``embedding_dimension``, ``supports_*``) and overrides
    only the embedding itself.
    """

    name = "lexical-hashing"

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]:
        del route_id, tenant_id, run_id, timeout_s
        return [lexical_embed(t, self._dim) for t in texts]


@dataclass
class InMemoryVectorStore:
    """Cosine-ranking store over pre-embedded chunks; enforces tenant + approved filters.

    Mirrors the production `VectorStore` invariants (ADR-0010): tenant isolation and approval
    filtering happen here, at the adapter boundary, before results reach the Retriever.
    """

    name: str = "in-memory-cosine"
    _entries: list[tuple[list[float], Chunk]] = field(default_factory=list)
    _dim: int = 1536

    async def upsert(self, *, payloads: list) -> None:  # pragma: no cover - unused offline
        raise NotImplementedError

    def index(self, *, vector: list[float], chunk: Chunk) -> None:
        self._entries.append((vector, chunk))

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[AdapterScoredChunk]:
        del sparse_query  # the offline store ranks on the dense (lexical) vector only
        scored: list[AdapterScoredChunk] = []
        for vector, chunk in self._entries:
            if chunk.tenant_id != filters.tenant_id:
                continue
            if filters.approved is True and not chunk.approved:
                continue
            score = sum(a * b for a, b in zip(query_vector, vector, strict=False))
            scored.append(AdapterScoredChunk(chunk=chunk, score=score))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    async def delete_by_filter(self, *, filters: VectorFilter) -> int:  # pragma: no cover
        del filters
        return 0

    @property
    def embedding_dimension(self) -> int:
        return self._dim


def load_fixture_chunks(*, tenant_id: str, dim: int = 1536) -> list[Chunk]:
    """Read the tiny fixture corpus into `Chunk` models, re-homed under ``tenant_id``.

    Includes the deliberately-unapproved chunk so the store's approval filter is exercised.
    """
    raw = json.loads(TINY_APPROVED_CORPUS.read_text(encoding="utf-8"))
    corpus_version = raw["corpusVersion"]
    chunks: list[Chunk] = []
    for source in raw["sources"]:
        for c in source["chunks"]:
            chunks.append(
                Chunk(
                    chunk_id=c["chunkId"],
                    source_id=source["sourceId"],
                    tenant_id=tenant_id,
                    text=c["text"],
                    chunk_hash=c["chunkHash"],
                    approved=c["approved"],
                    visibility=c.get("visibility", "member"),
                    embedding_model="lexical-hashing@offline",
                    embedding_dimension=dim,
                    corpus_version=corpus_version,
                    created_at=datetime.now(UTC),
                )
            )
    return chunks


def build_offline_index(chunks: Sequence[Chunk], *, dim: int = 1536) -> InMemoryVectorStore:
    store = InMemoryVectorStore(_dim=dim)
    for chunk in chunks:
        store.index(vector=lexical_embed(chunk.text, dim), chunk=chunk)
    return store


def _config_to_retrieval(label: ConfigLabel) -> RetrievalConfig | None:
    if label == "dense_only":
        return None
    if label == "hybrid":
        return RetrievalConfig(use_hybrid=True)
    return RetrievalConfig(
        use_hybrid=True, reranker=RetrievalRerankerConfig(enabled=True)
    )


# --------------------------------------------------------------------------------------------
# The harness
# --------------------------------------------------------------------------------------------
@dataclass
class RetrievalHarness:
    """Runs each gold-set case through A3 and returns `CaseResult`s for `metrics.aggregate`."""

    retriever: Retriever
    principal: Principal
    top_k: int = 20  # retrieve the deepest K once; metrics slice at 6/12/20

    async def run(
        self, gold_set: GoldSet, *, config: ConfigLabel = "dense_only"
    ) -> list[CaseResult]:
        results: list[CaseResult] = []
        retrieval = _config_to_retrieval(config)
        for case in gold_set.cases:
            plan = RetrievalPlan(
                semantic_query=case.query,
                answer_mode=_PLAN_ANSWER_MODE,
                tenant_id=self.principal.tenant_id,
                filters=RetrievalFilters(
                    tenant_id=self.principal.tenant_id, approved=True
                ),
                k=self.top_k,
                retrieval=retrieval,
            )
            outcome = await self.retriever.retrieve(
                plan=plan, principal=self.principal, run_id=f"reval-{case.id}"
            )
            results.append(
                CaseResult(
                    case_id=case.id,
                    retrieved_ids=[c.chunk.chunk_id for c in outcome.candidates],
                    expected_ids=list(case.expected_chunk_ids),
                    minimally_sufficient_ids=list(case.minimally_sufficient_chunk_ids),
                )
            )
        return results


class _OfflineSparseEmbedder:
    """Minimal sparse embedder so `use_hybrid` plans don't warn; ranking stays dense-only."""

    def embed(self, texts: list[str]) -> list[SparseVector]:
        return [SparseVector(indices=[0], values=[1.0]) for _ in texts]


def build_offline_harness(
    *, tenant_id: str = "tenant_smoke", role: str = "scholar", dim: int = 1536
) -> RetrievalHarness:
    """Assemble a fully offline harness over the fixture corpus (no network, no API cost)."""
    chunks = load_fixture_chunks(tenant_id=tenant_id, dim=dim)
    store = build_offline_index(chunks, dim=dim)
    retriever = Retriever(
        embedding_provider=LexicalEmbeddingProvider(dimension=dim),
        vector_store=store,
        sparse_embedder=_OfflineSparseEmbedder(),
        embedding_route_id="retrieval_eval_offline@1",
    )
    principal = make_dev_principal(tenant_id=tenant_id, role=role, user_id="usr_reval")
    return RetrievalHarness(retriever=retriever, principal=principal)


__all__ = [
    "ConfigLabel",
    "GoldCase",
    "GoldSet",
    "InMemoryVectorStore",
    "LexicalEmbeddingProvider",
    "RetrievalHarness",
    "TINY_APPROVED_CORPUS",
    "build_offline_harness",
    "build_offline_index",
    "lexical_embed",
    "load_fixture_chunks",
    "load_gold_set",
]
