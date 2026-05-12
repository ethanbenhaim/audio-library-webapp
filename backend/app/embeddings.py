"""
Abstract embedding interface + CLAP implementation.

Adding a new model:
1. Subclass EmbeddingModel and implement embed_audio / embed_text / dim.
2. Register it in _MODEL_REGISTRY at the bottom.
3. Set model_type in config.yaml.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel(ABC):
    """Common interface for audio-language embedding models."""

    @abstractmethod
    def embed_audio(self, file_path: str | Path) -> np.ndarray:
        """Return a 1-D normalised embedding vector for an audio file."""

    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Return a 1-D normalised embedding vector for a text query."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimensionality."""


# ---------------------------------------------------------------------------
# CLAP (Contrastive Language-Audio Pretraining)
# Paper: https://arxiv.org/abs/2211.06687
# HuggingFace: laion/larger_clap_general
# ---------------------------------------------------------------------------

class CLAPModel(EmbeddingModel):
    """
    CLAP maps audio and text into the same embedding space using contrastive
    pre-training — conceptually identical to CLIP but for audio.

    Supported HuggingFace model IDs:
      - laion/larger_clap_general   (recommended, general audio)
      - laion/larger_clap_music     (music-focused)
      - laion/clap-htsat-unfused    (lighter / faster)
    """

    # CLAP requires 48 kHz mono input
    TARGET_SR = 48_000

    def __init__(self, model_id: str = "laion/larger_clap_general", device: str = "cpu"):
        import torch
        from transformers import ClapModel as HFClapModel, ClapProcessor

        self._device = device
        logger.info("Loading CLAP model %s on %s …", model_id, device)

        self._processor = ClapProcessor.from_pretrained(model_id)
        self._model = HFClapModel.from_pretrained(model_id)
        self._model.to(device)
        self._model.eval()

        self._torch = torch
        self._dim = self._probe_dim()
        logger.info("CLAP ready — embedding dim: %d", self._dim)

    def _probe_dim(self) -> int:
        """Infer embedding dimension from a tiny dummy forward pass."""
        import torch
        dummy = np.zeros(self.TARGET_SR, dtype=np.float32)
        inputs = self._processor(
            audios=dummy,
            sampling_rate=self.TARGET_SR,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            feat = self._model.get_audio_features(**inputs)
        return feat.shape[-1]

    @property
    def dim(self) -> int:
        return self._dim

    def embed_audio(self, file_path: str | Path) -> np.ndarray:
        import librosa, torch

        audio, _ = librosa.load(str(file_path), sr=self.TARGET_SR, mono=True)
        inputs = self._processor(
            audios=audio,
            sampling_rate=self.TARGET_SR,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            features = self._model.get_audio_features(**inputs)
        vec = features.cpu().numpy()[0]
        return vec / (np.linalg.norm(vec) + 1e-8)

    def embed_text(self, text: str) -> np.ndarray:
        import torch

        inputs = self._processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            features = self._model.get_text_features(**inputs)
        vec = features.cpu().numpy()[0]
        return vec / (np.linalg.norm(vec) + 1e-8)


# ---------------------------------------------------------------------------
# Registry + factory
# ---------------------------------------------------------------------------

_MODEL_REGISTRY: dict[str, type[EmbeddingModel]] = {
    "clap": CLAPModel,
}

# Module-level singleton (lazy-initialised in the Celery worker process)
_instance: EmbeddingModel | None = None


def get_embedding_model(model_type: str | None = None, model_id: str | None = None, device: str | None = None) -> EmbeddingModel:
    """
    Return the module-level singleton embedding model, initialising it on first call.
    Falls back to config.yaml values for any parameter that is None.
    """
    global _instance
    if _instance is None:
        from .config import config

        mt = model_type or config.embedding.model_type
        mi = model_id or config.embedding.model_id
        dev = device or config.embedding.device

        cls = _MODEL_REGISTRY.get(mt)
        if cls is None:
            raise ValueError(
                f"Unknown embedding model_type '{mt}'. "
                f"Registered types: {list(_MODEL_REGISTRY)}"
            )

        _instance = cls(model_id=mi, device=dev)

    return _instance
