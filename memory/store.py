"""
memory/store.py
---------------
A lightweight semantic memory layer backed by ChromaDB.

The agent can:
  - store(text, metadata)  → persist a finding with optional tags
  - search(query, k)       → retrieve the k most relevant past findings
  - clear()                → reset memory between research sessions

ChromaDB runs fully in-process (no server needed) and persists to disk
at the path set by CHROMA_PERSIST_DIR (default: ./chroma_db).
"""

from __future__ import annotations

import os
import uuid
import json
from typing import Any

_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

try:
    import chromadb
    from chromadb.config import Settings

    _client = chromadb.PersistentClient(
        path=_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name="research_memory",
        metadata={"hnsw:space": "cosine"},
    )
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
    _collection = None


# ── In-process fallback (list-based) used when ChromaDB is not installed ─────

_FALLBACK_STORE: list[dict] = []


def store(text: str, metadata: dict[str, Any] | None = None) -> str:
    """Persist a piece of text (finding, snippet, URL summary) to memory.

    Args:
        text:     The content to remember.
        metadata: Optional dict with tags like {"task": "...", "source": "..."}.

    Returns:
        The auto-generated document ID.
    """
    doc_id = str(uuid.uuid4())
    meta = metadata or {}

    if _CHROMA_AVAILABLE and _collection is not None:
        _collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
        )
    else:
        _FALLBACK_STORE.append({"id": doc_id, "text": text, "meta": meta})

    return doc_id


def search(query: str, k: int = 5) -> list[dict]:
    """Retrieve the k most semantically similar stored documents.

    Args:
        query: Natural-language query to match against stored findings.
        k:     Number of results to return.

    Returns:
        List of dicts with keys: id, text, metadata, distance.
    """
    if _CHROMA_AVAILABLE and _collection is not None:
        count = _collection.count()
        if count == 0:
            return []
        results = _collection.query(
            query_texts=[query],
            n_results=min(k, count),
        )
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        ids = results["ids"][0]
        dists = results["distances"][0]
        return [
            {"id": ids[i], "text": docs[i], "metadata": metas[i], "distance": dists[i]}
            for i in range(len(docs))
        ]
    else:
        # Naïve keyword fallback
        ql = query.lower()
        scored = [
            (sum(w in item["text"].lower() for w in ql.split()), item)
            for item in _FALLBACK_STORE
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": item["id"], "text": item["text"], "metadata": item["meta"], "distance": 0.0}
            for _, item in scored[:k]
        ]


def clear() -> None:
    """Delete all stored documents (call between independent research sessions)."""
    if _CHROMA_AVAILABLE and _collection is not None:
        existing = _collection.get()["ids"]
        if existing:
            _collection.delete(ids=existing)
    else:
        _FALLBACK_STORE.clear()


def count() -> int:
    """Return the number of stored documents."""
    if _CHROMA_AVAILABLE and _collection is not None:
        return _collection.count()
    return len(_FALLBACK_STORE)
