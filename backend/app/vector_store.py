"""
Qdrant vector store wrapper.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, config):
        from qdrant_client import QdrantClient
        from pathlib import Path

        self._collection = config.collection

        if config.mode == "local":
            # Embedded in-process Qdrant — no server or Docker needed
            local_path = (Path(__file__).parent.parent / config.local_path).resolve()
            local_path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(local_path))
            logger.info("Using local Qdrant at %s", local_path)
        else:
            self._client = QdrantClient(host=config.host, port=config.port)
            logger.info("Connected to Qdrant server at %s:%d", config.host, config.port)

    def ensure_collection(self, dim: int) -> None:
        """Create the collection if it does not exist."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s' (dim=%d)", self._collection, dim)

    def upsert(self, file_id: int, vector: np.ndarray, payload: dict[str, Any]) -> None:
        from qdrant_client.models import PointStruct

        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=file_id,
                    vector=vector.tolist(),
                    payload=payload,
                )
            ],
        )

    def search(
        self,
        query_vector: np.ndarray,
        limit: int = 20,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector.tolist(),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"id": r.id, "score": r.score, **(r.payload or {})}
            for r in response.points
        ]

    def retrieve_vector(self, file_id: int) -> np.ndarray | None:
        """Fetch the stored embedding vector for a single point."""
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[file_id],
            with_vectors=True,
        )
        if not points:
            return None
        return np.array(points[0].vector)

    def delete(self, file_id: int) -> None:
        from qdrant_client.models import PointIdsList

        self._client.delete(
            collection_name=self._collection,
            points_selector=PointIdsList(points=[file_id]),
        )


# Module-level singleton
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        from .config import config
        _store = VectorStore(config.qdrant)
    return _store
