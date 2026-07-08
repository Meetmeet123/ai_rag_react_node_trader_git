"""
Cross-Encoder Reranker for TradeForge RAG

Re-ranks initially retrieved documents using a cross-encoder model that
jointly encodes ``(query, document)`` pairs.  This yields far more
accurate relevance scores than bi-encoder (embedding) similarity alone,
because the cross-encoder can attend to interactions between query and
document tokens.

Additional ranking signals:
* **Diversity** – penalises redundant content from the same source.
* **Freshness** – boosts recently created documents.
* **Source balancing** – caps the number of results per source to ensure
  variety and prevent any single collection from dominating the context.

The reranker is the final stage of the retrieval pipeline before context
is injected into the LLM prompt.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from sentence_transformers import CrossEncoder

# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class Reranker:
    """Cross-encoder reranker with diversity, freshness, and source balancing.

    The pipeline:
    1. Score every ``(query, doc)`` pair with the cross-encoder.
    2. Merge cross-encoder scores with original retrieval scores.
    3. Apply diversity penalty (similar-source documents are down-ranked).
    4. Apply freshness boost (recent documents are up-ranked).
    5. Enforce source-balancing caps.
    6. Return the final top-k.

    Parameters
    ----------
    model_name:
        Hugging-Face model identifier for the cross-encoder.
    diversity_weight:
        Strength of the diversity penalty (0.0 = disabled).
    freshness_weight:
        Strength of the freshness boost (0.0 = disabled).
    max_per_source:
        Maximum documents to keep from any single source.
    device:
        PyTorch device (``"cpu"``, ``"cuda"``).
    batch_size:
        Batch size for cross-encoder inference.

    Example
    -------
    >>> reranker = Reranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    >>> ranked = reranker.rerank(
    ...     query="RSI mean reversion strategy",
    ...     documents=retrieved_docs,
    ...     top_k=5,
    ... )
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        diversity_weight: float = 0.1,
        freshness_weight: float = 0.15,
        max_per_source: int = 3,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.diversity_weight = diversity_weight
        self.freshness_weight = freshness_weight
        self.max_per_source = max_per_source
        self.device = device
        self.batch_size = batch_size

        logger.info(f"Loading cross-encoder reranker: {model_name} on {device}")
        self.cross_encoder = CrossEncoder(model_name, device=device)
        logger.info("Cross-encoder loaded successfully")

    # ===================================================================
    # Main API
    # ===================================================================

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        merge_with_original: bool = True,
        original_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Re-rank a list of documents using the cross-encoder.

        Parameters
        ----------
        query:
            Original user query (the cross-encoder jointly encodes
            ``query + document``).
        documents:
            Retrieved documents.  Each dict must have at least a
            ``"content"`` key.  Optional keys: ``"score"`` (original
            retrieval score), ``"metadata"`` (with ``"source"``,
            ``"timestamp"``), ``"doc_id"``.
        top_k:
            Number of final documents to return.
        merge_with_original:
            If ``True``, blend cross-encoder scores with the original
            retrieval scores.
        original_weight:
            Weight given to the original score when merging (0.0 … 1.0).

        Returns
        -------
        list[dict]
            Re-ranked documents, highest relevance first.  Each dict
            includes the original keys plus ``"rerank_score"`` and
            ``"rank"``.

        Raises
        ------
        ValueError
            If ``documents`` is empty or missing required fields.
        """
        if not documents:
            return []

        if not all("content" in d for d in documents):
            raise ValueError("All documents must have a 'content' field")

        t0 = time.perf_counter()

        # Stage 1 – cross-encoder scoring
        ce_scores = self._compute_cross_encoder_scores(query, documents)

        # Stage 2 – merge with original scores
        for i, doc in enumerate(documents):
            doc["rerank_score"] = ce_scores[i]
            if merge_with_original and "score" in doc:
                doc["final_score"] = (1.0 - original_weight) * ce_scores[
                    i
                ] + original_weight * doc["score"]
            else:
                doc["final_score"] = ce_scores[i]

        # Stage 3 – diversity penalty
        if self.diversity_weight > 0:
            documents = self._apply_diversity_penalty(documents)

        # Stage 4 – freshness boost
        if self.freshness_weight > 0:
            documents = self._apply_freshness_boost(documents)

        # Stage 5 – source balancing
        documents = self._source_balancing(documents)

        # Stage 6 – final sort and truncate
        documents.sort(key=lambda d: d["final_score"], reverse=True)

        for i, doc in enumerate(documents):
            doc["rank"] = i + 1

        elapsed = (time.perf_counter() - t0) * 1000.0
        logger.info(
            f"Reranked {len(documents)} documents in {elapsed:.1f} ms → top {top_k}"
        )

        return documents[:top_k]

    def rerank_batch(
        self,
        queries: List[str],
        documents_per_query: List[List[Dict[str, Any]]],
        top_k: int = 5,
    ) -> List[List[Dict[str, Any]]]:
        """Re-rank documents for multiple queries in a single batch.

        This is more efficient than calling ``rerank`` repeatedly because
        it amortises model loading overhead.

        Parameters
        ----------
        queries:
            One query string per query group.
        documents_per_query:
            List of document lists, one per query.
        top_k:
            Number of results per query.

        Returns
        -------
        list[list[dict]]
            Re-ranked documents for each query.
        """
        if len(queries) != len(documents_per_query):
            raise ValueError("queries and documents_per_query must have same length")

        results = []
        for query, docs in zip(queries, documents_per_query):
            results.append(self.rerank(query, docs, top_k=top_k))
        return results

    # ===================================================================
    # Scoring
    # ===================================================================

    def _compute_cross_encoder_scores(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[float]:
        """Compute cross-encoder relevance scores for all query-document pairs.

        Returns a list of scores in [0, 1] (sigmoid-normalised).
        """
        pairs = [
            (query, doc["content"][:2048]) for doc in documents
        ]  # truncate long docs

        # Predict in batches for efficiency
        raw_scores = self.cross_encoder.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # Normalise to [0, 1] using sigmoid (cross-encoders output logits)
        scores = 1.0 / (1.0 + np.exp(-raw_scores))
        return scores.tolist()

    # ===================================================================
    # Post-processing signals
    # ===================================================================

    def _apply_diversity_penalty(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Penalise documents whose content is too similar to higher-ranked ones.

        Uses a simple source-overlap heuristic: if multiple consecutive
        documents come from the same source, each subsequent one receives
        a small penalty.  This ensures the final list contains a mix of
        strategy descriptions, backtest summaries, market context, etc.
        """
        if not documents:
            return documents

        # Track source occurrences
        source_counts: Dict[str, int] = {}

        for i, doc in enumerate(documents):
            source = self._get_doc_source(doc)
            count = source_counts.get(source, 0)

            # Penalty increases with each additional doc from same source
            penalty = self.diversity_weight * count
            doc["final_score"] = max(0.0, doc["final_score"] - penalty)

            source_counts[source] = count + 1

        return documents

    def _apply_freshness_boost(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Boost scores for more recent documents.

        Uses exponential decay: a document from *t* hours ago gets a
        boost factor of ``2^(-t/24)`` so that 24-hour-old documents
        receive roughly half the maximum boost.
        """
        now = datetime.utcnow()
        half_life_hours = 24.0

        for doc in documents:
            ts = self._get_doc_timestamp(doc)
            if ts is None:
                continue

            age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
            # Boost factor: 1.0 for brand-new, decays over time
            boost = self.freshness_weight * (2.0 ** (-age_hours / half_life_hours))
            doc["final_score"] = min(1.0, doc["final_score"] + boost)

        return documents

    def _source_balancing(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Enforce a maximum number of documents per source.

        This prevents any single collection from dominating the context
        window (e.g. 10 news articles crowding out strategy references).

        The algorithm is greedy: walk the already-sorted list and keep
        documents until the per-source cap is reached.
        """
        if self.max_per_source <= 0:
            return documents

        source_counts: Dict[str, int] = {}
        balanced: List[Dict[str, Any]] = []

        for doc in documents:
            source = self._get_doc_source(doc)
            count = source_counts.get(source, 0)
            if count < self.max_per_source:
                balanced.append(doc)
                source_counts[source] = count + 1

        return balanced

    # ===================================================================
    # Helpers
    # ===================================================================

    @staticmethod
    def _get_doc_source(doc: Dict[str, Any]) -> str:
        """Extract source name from document metadata."""
        meta = doc.get("metadata", {})
        if isinstance(meta, dict):
            return meta.get("source", meta.get("doc_type", "unknown"))
        return "unknown"

    @staticmethod
    def _get_doc_timestamp(doc: Dict[str, Any]) -> Optional[datetime]:
        """Best-effort timestamp extraction from document metadata."""
        meta = doc.get("metadata", {})
        if not isinstance(meta, dict):
            return None

        for key in (
            "timestamp",
            "published_at",
            "created_at",
            "entry_time",
            "updated_at",
        ):
            val = meta.get(key)
            if val is None:
                continue
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in (
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                ):
                    try:
                        return datetime.strptime(val.split("+")[0], fmt)
                    except ValueError:
                        continue
        return None

    # ===================================================================
    # Configuration
    # ===================================================================

    def set_diversity_weight(self, weight: float) -> None:
        """Update the diversity penalty strength."""
        if not 0.0 <= weight <= 1.0:
            raise ValueError("diversity_weight must be in [0, 1]")
        self.diversity_weight = weight
        logger.info(f"Diversity weight set to {weight}")

    def set_freshness_weight(self, weight: float) -> None:
        """Update the freshness boost strength."""
        if not 0.0 <= weight <= 1.0:
            raise ValueError("freshness_weight must be in [0, 1]")
        self.freshness_weight = weight
        logger.info(f"Freshness weight set to {weight}")

    def set_max_per_source(self, max_docs: int) -> None:
        """Update the per-source cap."""
        if max_docs < 1:
            raise ValueError("max_per_source must be >= 1")
        self.max_per_source = max_docs
        logger.info(f"Max per source set to {max_docs}")

    def get_config(self) -> Dict[str, Any]:
        """Return current reranker configuration."""
        return {
            "model_name": self.model_name,
            "diversity_weight": self.diversity_weight,
            "freshness_weight": self.freshness_weight,
            "max_per_source": self.max_per_source,
            "device": self.device,
            "batch_size": self.batch_size,
        }
