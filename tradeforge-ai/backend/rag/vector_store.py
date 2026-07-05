"""
ChromaDB Vector Store for TradeForge RAG

Manages multiple collections:
- strategies: All trading strategies with embeddings
- backtest_results: Backtest performance data
- market_regime: Market conditions and regime info
- news_events: Market news and events
- indicator_context: Technical indicator explanations
- trade_history: Executed trades log
- market_commentary: Market analysis and commentary

Uses sentence-transformers for local embeddings (no API cost).
Supports hybrid search (semantic + keyword via BM25-style scoring).
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import numpy as np
from chromadb.config import Settings
from loguru import logger
from sentence_transformers import SentenceTransformer

from .models import BaseDocument


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """Unified document format for RAG ingestion and retrieval.

    Attributes:
        id: Unique document identifier (MD5 hash of content + metadata).
        content: Raw text content to be embedded and stored.
        metadata: Arbitrary key-value metadata for filtering.
        embedding: Pre-computed embedding vector (optional).
        score: Retrieval / relevance score (populated after search).
    """

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: float = 0.0


@dataclass
class SearchResult:
    """Container for a single vector-store search operation.

    Attributes:
        documents: Ranked list of ``Document`` objects.
        total_found: Number of raw matches before cut-off.
        search_time_ms: Wall-clock time for the search.
        collection: Name of the ChromaDB collection queried.
    """

    documents: List[Document]
    total_found: int
    search_time_ms: float
    collection: str


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class VectorStore:
    """Production-grade vector store backed by ChromaDB.

    Features
    --------
    * Multiple named collections (strategies, backtest_results, …).
    * Local ``sentence-transformers`` embeddings – zero API cost.
    * Metadata filtering (time-range, symbol, segment, etc.).
    * Persistent storage (DuckDB + Parquet) with automatic sync.
    * Batch ingestion for high-throughput pipelines.
    * Hybrid search that blends dense vector similarity with a
      lightweight BM25-style keyword score.

    Parameters
    ----------
    persist_dir:
        Directory where ChromaDB writes its Parquet files.
    embedding_model:
        Hugging-Face model name for the bi-encoder embedder.
    device:
        PyTorch device – ``"cpu"``, ``"cuda"``, or ``"mps"``.

    Example
    -------
    >>> store = VectorStore(persist_dir="./data/chromadb", device="cpu")
    >>> doc = Document(
    ...     id="strat_001",
    ...     content="RSI mean-reversion on NIFTY50 ...",
    ...     metadata={"symbol": "NIFTY50", "win_rate": 62.5},
    ... )
    >>> store.add_documents("strategies", [doc])
    >>> result = store.search("strategies", "RSI oversold strategy", top_k=5)
    >>> for d in result.documents:
    ...     print(f"{d.score:.3f}  {d.content[:80]}")
    """

    # Collections that the RAG pipeline expects
    _COLLECTION_NAMES: Tuple[str, ...] = (
        "strategies",
        "backtest_results",
        "market_regime",
        "news_events",
        "indicator_context",
        "trade_history",
        "market_commentary",
    )

    # ------------------------------------------------------------------
    # Construction / init
    # ------------------------------------------------------------------

    def __init__(
        self,
        persist_dir: str = "./data/chromadb",
        embedding_model: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        self.persist_dir = persist_dir
        self.embedding_model_name = embedding_model
        self.device = device

        os.makedirs(persist_dir, exist_ok=True)

        # ChromaDB persistent client (DuckDB + Parquet backend)
        logger.info(f"Initialising ChromaDB  persistent store → {persist_dir}")
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )

        # Local embedder – free, fast, offline-capable
        logger.info(f"Loading embedding model '{embedding_model}' on {device}")
        self.embedder = SentenceTransformer(embedding_model, device=device)
        self.embedding_dim: int = self.embedder.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")

        # Lazy-loaded collection cache
        self._collections: Dict[str, chromadb.Collection] = {}
        self._init_collections()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_collections(self) -> None:
        """Create (or open) every collection defined in ``_COLLECTION_NAMES``."""
        for name in self._COLLECTION_NAMES:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={
                    "created_at": datetime.utcnow().isoformat(),
                    "embedding_model": self.embedding_model_name,
                    "embedding_dim": str(self.embedding_dim),
                },
            )
            logger.info(f"Collection ready: {name}")

    def _get_collection(self, name: str) -> chromadb.Collection:
        """Return a cached collection, raising if unknown."""
        if name not in self._collections:
            raise ValueError(
                f"Unknown collection '{name}'. "
                f"Available: {list(self._collections.keys())}"
            )
        return self._collections[name]

    def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of texts into dense vectors."""
        if not texts:
            return []
        vectors = self.embedder.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine similarity
            show_progress_bar=False,
        )
        return vectors.tolist()

    @staticmethod
    def _compute_id(content: str, metadata: Optional[Dict] = None) -> str:
        """Deterministic MD5 ID from content + sorted metadata JSON."""
        payload = content + json.dumps(metadata or {}, sort_keys=True)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _bm25_score(query_tokens: set, doc_text: str) -> float:
        """Lightweight BM25-style keyword overlap score.

        This is a simplified static scoring function (no IDF, no length
        normalisation) intended *only* as a supplement to dense similarity.
        It is fast, has zero external dependencies, and works well for
        short financial documents.
        """
        if not query_tokens:
            return 0.0
        doc_tokens = set(doc_text.lower().split())
        overlap = len(query_tokens & doc_tokens)
        return overlap / len(query_tokens)  # 0.0 … 1.0

    @staticmethod
    def _build_where_filter(
        filters: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Convert a flat dict of metadata filters into ChromaDB ``where`` syntax.

        Supports exact match, ``$gt``, ``$gte``, ``$lt``, ``$lte``, ``$ne``,
        and ``$in`` operators by prefixing the value string with the operator.

        Examples
        --------
        >>> VectorStore._build_where_filter({"symbol": "RELIANCE"})
        {'symbol': {'$eq': 'RELIANCE'}}

        >>> VectorStore._build_where_filter({"win_rate": "gte:60"})
        {'win_rate': {'$gte': 60.0}}
        """
        if not filters:
            return None

        conditions: List[Dict[str, Any]] = []
        for key, raw_val in filters.items():
            if isinstance(raw_val, str) and ":" in raw_val and raw_val.split(":", 1)[0] in {
                "gt", "gte", "lt", "lte", "ne", "in",
            }:
                op, val_str = raw_val.split(":", 1)
                if op == "in":
                    parsed = val_str.split(",")
                else:
                    parsed = _coerce_numeric(val_str)
                conditions.append({key: {f"${op}": parsed}})
            elif isinstance(raw_val, list):
                conditions.append({key: {"$in": raw_val}})
            else:
                conditions.append({key: {"$eq": _coerce_numeric(raw_val)}})

        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ------------------------------------------------------------------
    # Public API – CRUD
    # ------------------------------------------------------------------

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
        batch_size: int = 100,
    ) -> int:
        """Add documents to a collection, computing embeddings automatically.

        Documents are processed in configurable batches to keep memory
        consumption predictable even for large ingestion jobs.

        Parameters
        ----------
        collection_name:
            Target collection name.
        documents:
            List of ``Document`` instances to store.
        batch_size:
            Number of documents whose embeddings are computed in one pass.

        Returns
        -------
        int
            Number of documents successfully added.

        Raises
        ------
        ValueError
            If ``collection_name`` is not a known collection.
        """
        collection = self._get_collection(collection_name)
        total_added = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ids: List[str] = []
            texts: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for doc in batch:
                doc_id = doc.id or self._compute_id(doc.content, doc.metadata)
                ids.append(doc_id)
                texts.append(doc.content)
                metadatas.append(doc.metadata)

            try:
                embeddings = self._compute_embeddings(texts)
                collection.add(
                    ids=ids,
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                total_added += len(batch)
                logger.debug(
                    f"Added {len(batch)} docs to '{collection_name}' "
                    f"(batch {i // batch_size + 1})"
                )
            except Exception as exc:
                logger.error(f"Batch insert failed for '{collection_name}': {exc}")
                raise

        logger.info(
            f"Added {total_added}/{len(documents)} documents to '{collection_name}'"
        )
        return total_added

    def update_document(
        self,
        collection_name: str,
        document: Document,
    ) -> bool:
        """Update (overwrite) a single document by its ``id``.

        Returns ``True`` on success, ``False`` if the document did not exist.
        """
        collection = self._get_collection(collection_name)
        if not document.id:
            document.id = self._compute_id(document.content, document.metadata)

        try:
            collection.update(
                ids=[document.id],
                documents=[document.content],
                embeddings=[self.embed_text(document.content)],
                metadatas=[document.metadata],
            )
            logger.debug(f"Updated document {document.id} in '{collection_name}'")
            return True
        except Exception as exc:
            logger.warning(f"Update failed for {document.id}: {exc}")
            return False

    def upsert_documents(
        self,
        collection_name: str,
        documents: List[Document],
        batch_size: int = 100,
    ) -> int:
        """Upsert documents – insert if new, overwrite if existing."""
        collection = self._get_collection(collection_name)
        total_upserted = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            ids, texts, metadatas = [], [], []

            for doc in batch:
                doc_id = doc.id or self._compute_id(doc.content, doc.metadata)
                ids.append(doc_id)
                texts.append(doc.content)
                metadatas.append(doc.metadata)

            embeddings = self._compute_embeddings(texts)
            collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_upserted += len(batch)

        logger.info(f"Upserted {total_upserted} docs into '{collection_name}'")
        return total_upserted

    def get_document(
        self,
        collection_name: str,
        doc_id: str,
    ) -> Optional[Document]:
        """Fetch a single document by ID."""
        collection = self._get_collection(collection_name)
        try:
            result = collection.get(ids=[doc_id], include=["documents", "metadatas", "embeddings"])
            if not result["ids"]:
                return None
            return Document(
                id=result["ids"][0],
                content=result["documents"][0] or "",
                metadata=result["metadatas"][0] or {},
                embedding=result["embeddings"][0] if result.get("embeddings") else None,
            )
        except Exception as exc:
            logger.error(f"Failed to get document {doc_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Public API – Search
    # ------------------------------------------------------------------

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> SearchResult:
        """Dense semantic search in a single collection.

        Parameters
        ----------
        collection_name:
            Collection to query.
        query:
            Free-text query.
        top_k:
            Maximum number of results to return.
        filters:
            Metadata filters (e.g. ``{"symbol": "RELIANCE"}``).
        min_score:
            Minimum cosine-similarity score (0.0 … 1.0).

        Returns
        -------
        SearchResult
            Ranked list of matching documents with timing info.
        """
        t0 = time.perf_counter()
        collection = self._get_collection(collection_name)
        query_embedding = self._compute_embeddings([query])[0]
        where_clause = self._build_where_filter(filters)

        try:
            raw = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,  # over-fetch for post-filtering
                where=where_clause,
                include=["documents", "metadatas", "distances", "embeddings"],
            )
        except Exception as exc:
            logger.error(f"Search failed on '{collection_name}': {exc}")
            return SearchResult(documents=[], total_found=0, search_time_ms=0.0, collection=collection_name)

        documents: List[Document] = []
        if raw["ids"] and raw["ids"][0]:
            for idx, doc_id in enumerate(raw["ids"][0]):
                distance = raw["distances"][0][idx] if raw["distances"] else 1.0
                # ChromaDB returns L2 distance; convert to cosine similarity
                score = 1.0 - (distance / 2.0) if distance <= 2.0 else 0.0

                if score < min_score:
                    continue

                documents.append(
                    Document(
                        id=doc_id,
                        content=raw["documents"][0][idx] or "",
                        metadata=raw["metadatas"][0][idx] or {},
                        embedding=raw["embeddings"][0][idx] if raw.get("embeddings") else None,
                        score=round(score, 6),
                    )
                )

        documents.sort(key=lambda d: d.score, reverse=True)
        documents = documents[:top_k]
        elapsed = (time.perf_counter() - t0) * 1000.0

        logger.info(
            f"Search '{collection_name}': query='{query[:50]}…' → "
            f"{len(documents)} results in {elapsed:.1f} ms"
        )
        return SearchResult(
            documents=documents,
            total_found=len(documents),
            search_time_ms=elapsed,
            collection=collection_name,
        )

    def hybrid_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> SearchResult:
        """Hybrid search combining dense semantic + BM25 keyword scoring.

        The final score of each candidate is::

            final = semantic_weight * cosine_sim + keyword_weight * bm25_score

        Parameters
        ----------
        keyword_weight:
            Relative importance of keyword overlap (0.0 … 1.0).
        semantic_weight:
            Relative importance of vector similarity (0.0 … 1.0).

        Returns
        -------
        SearchResult
            Documents ranked by the blended hybrid score.
        """
        if not (0.0 <= keyword_weight <= 1.0 and 0.0 <= semantic_weight <= 1.0):
            raise ValueError("Weights must be in [0, 1]")
        if abs(keyword_weight + semantic_weight - 1.0) > 1e-6:
            raise ValueError("keyword_weight + semantic_weight must equal 1.0")

        t0 = time.perf_counter()
        collection = self._get_collection(collection_name)
        query_embedding = self._compute_embeddings([query])[0]
        query_tokens = set(query.lower().split())
        where_clause = self._build_where_filter(filters)

        # Over-fetch so we have candidates for both signals
        n_fetch = max(top_k * 4, 50)
        try:
            raw = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_fetch,
                where=where_clause,
                include=["documents", "metadatas", "distances", "embeddings"],
            )
        except Exception as exc:
            logger.error(f"Hybrid search failed on '{collection_name}': {exc}")
            return SearchResult(documents=[], total_found=0, search_time_ms=0.0, collection=collection_name)

        if not raw["ids"] or not raw["ids"][0]:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return SearchResult(documents=[], total_found=0, search_time_ms=elapsed, collection=collection_name)

        candidates: List[Document] = []
        for idx, doc_id in enumerate(raw["ids"][0]):
            distance = raw["distances"][0][idx] if raw["distances"] else 1.0
            semantic_score = max(0.0, 1.0 - (distance / 2.0))
            doc_text = raw["documents"][0][idx] or ""
            keyword_score = self._bm25_score(query_tokens, doc_text)

            hybrid_score = semantic_weight * semantic_score + keyword_weight * keyword_score

            if hybrid_score < min_score:
                continue

            candidates.append(
                Document(
                    id=doc_id,
                    content=doc_text,
                    metadata=raw["metadatas"][0][idx] or {},
                    embedding=raw["embeddings"][0][idx] if raw.get("embeddings") else None,
                    score=round(hybrid_score, 6),
                )
            )

        candidates.sort(key=lambda d: d.score, reverse=True)
        candidates = candidates[:top_k]
        elapsed = (time.perf_counter() - t0) * 1000.0

        logger.info(
            f"Hybrid search '{collection_name}': '{query[:50]}…' → "
            f"{len(candidates)} results in {elapsed:.1f} ms"
        )
        return SearchResult(
            documents=candidates,
            total_found=len(candidates),
            search_time_ms=elapsed,
            collection=collection_name,
        )

    def multi_collection_search(
        self,
        query: str,
        collections: List[str],
        top_k_per_collection: int = 3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, SearchResult]:
        """Search across multiple collections and return per-collection results.

        This is *synchronous* and executes searches sequentially.  For true
        parallelism use ``await`` wrappers or thread pools in the caller.

        Returns
        -------
        dict
            Mapping ``collection_name → SearchResult``.
        """
        results: Dict[str, SearchResult] = {}
        for coll_name in collections:
            if coll_name not in self._collections:
                logger.warning(f"Skipping unknown collection '{coll_name}'")
                continue
            try:
                results[coll_name] = self.search(
                    collection_name=coll_name,
                    query=query,
                    top_k=top_k_per_collection,
                    filters=filters,
                )
            except Exception as exc:
                logger.error(f"Search failed on '{coll_name}': {exc}")
                results[coll_name] = SearchResult(
                    documents=[], total_found=0, search_time_ms=0.0, collection=coll_name
                )
        return results

    # ------------------------------------------------------------------
    # Public API – Deletion / stats / maintenance
    # ------------------------------------------------------------------

    def delete_by_filter(self, collection_name: str, filters: Dict[str, Any]) -> int:
        """Delete all documents whose metadata matches *all* supplied filters.

        Returns the number of documents deleted.
        """
        collection = self._get_collection(collection_name)
        where_clause = self._build_where_filter(filters)
        if where_clause is None:
            raise ValueError("filters cannot be empty for delete_by_filter")

        try:
            # ChromaDB requires IDs for deletion; we must fetch first
            matches = collection.get(where=where_clause, include=[])
            ids_to_delete = matches.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(
                    f"Deleted {len(ids_to_delete)} documents from '{collection_name}'"
                )
            return len(ids_to_delete)
        except Exception as exc:
            logger.error(f"Delete failed on '{collection_name}': {exc}")
            return 0

    def delete_by_ids(self, collection_name: str, doc_ids: List[str]) -> int:
        """Delete documents by their IDs."""
        collection = self._get_collection(collection_name)
        if not doc_ids:
            return 0
        try:
            collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents from '{collection_name}'")
            return len(doc_ids)
        except Exception as exc:
            logger.error(f"Delete by IDs failed: {exc}")
            return 0

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Return statistics for a single collection."""
        collection = self._get_collection(collection_name)
        try:
            count = collection.count()
            peek = collection.peek(limit=1)
            return {
                "name": collection_name,
                "document_count": count,
                "embedding_model": self.embedding_model_name,
                "embedding_dim": self.embedding_dim,
                "persist_dir": self.persist_dir,
                "has_data": count > 0,
                "sample_id": peek["ids"][0] if peek.get("ids") else None,
            }
        except Exception as exc:
            logger.error(f"Stats failed for '{collection_name}': {exc}")
            return {"name": collection_name, "error": str(exc)}

    def get_all_stats(self) -> Dict[str, Any]:
        """Return statistics for *all* collections."""
        return {
            "store": {
                "persist_dir": self.persist_dir,
                "embedding_model": self.embedding_model_name,
                "embedding_dim": self.embedding_dim,
                "device": self.device,
            },
            "collections": {
                name: self.get_collection_stats(name)
                for name in self._collections
            },
        }

    def embed_text(self, text: str) -> List[float]:
        """Encode a single text string into an embedding vector."""
        return self._compute_embeddings([text])[0]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple text strings into embedding vectors."""
        return self._compute_embeddings(texts)

    def persist(self) -> None:
        """Force ChromaDB to persist current state to disk.

        With the PersistentClient this is generally automatic on mutation,
        but explicit calls are useful before long-running operations.
        """
        logger.info("Persisting ChromaDB state to disk")
        # PersistentClient auto-persists; this method exists for API symmetry
        # and future-proofing against custom backends.

    def close(self) -> None:
        """Clean shutdown – persists state and releases resources."""
        logger.info("Closing VectorStore")
        self.persist()
        # SentenceTransformer has no explicit close, but we can help GC
        del self.embedder

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _coerce_numeric(val: Any) -> Any:
    """Try to convert *val* to ``int`` or ``float``; fall back to string."""
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, str):
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            return val
    return val
