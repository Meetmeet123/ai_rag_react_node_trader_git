"""
TradeForge AI — RAG service singleton.

Provides lazy initialisation of the :class:`TradeForgeRAG` engine and a
fault-tolerant accessor that returns ``None`` when RAG cannot be started.
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from config import settings
from rag.rag_engine import TradeForgeRAG

_rag_instance: Optional[TradeForgeRAG] = None


def _vector_store_dir() -> str:
    return os.path.join(settings.DATA_DIR, "chromadb")


def get_rag() -> TradeForgeRAG:
    """Return the initialised ``TradeForgeRAG`` singleton.

    The engine is created on first call using application settings.
    Subsequent calls return the same instance.
    """
    global _rag_instance
    if _rag_instance is None:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        os.makedirs(_vector_store_dir(), exist_ok=True)

        _rag_instance = TradeForgeRAG(
            vector_store_dir=_vector_store_dir(),
            device="cpu",
        )
        _rag_instance.initialize()
    return _rag_instance


def get_rag_or_none() -> Optional[TradeForgeRAG]:
    """Return the RAG engine, or ``None`` if it cannot be initialised.

    This accessor is safe to use in request handlers where RAG should be
    best-effort rather than required.
    """
    try:
        return get_rag()
    except Exception as exc:
        logger.warning("RAG engine unavailable: {}", exc)
        return None
