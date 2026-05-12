"""
Celery tasks for audio ingestion pipeline.

Flow per file:
  1. Extract metadata + waveform peaks → SQLite
  2. Generate CLAP embedding → Qdrant

Progress is reported via Celery task state so the frontend can poll it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from celery import states
from celery.exceptions import Ignore

from .celery_app import celery_app
from .config import config

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.ingest_folder")
def ingest_folder(self, folder_path: str, reindex: bool = False) -> dict:
    """
    Ingest all supported audio files under folder_path.

    Args:
        folder_path: Absolute or relative path to the folder.
        reindex: If True, re-embed files that were already indexed.

    Returns:
        Summary dict with counts.
    """
    from .database import SessionLocal
    from .embeddings import get_embedding_model
    from .ingestion import extract_metadata, generate_waveform_peaks, scan_folder
    from .models import AudioFile
    from .vector_store import get_vector_store

    # --- 1. Scan ---
    try:
        files = scan_folder(folder_path)
    except ValueError as exc:
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()

    total = len(files)
    if total == 0:
        return {"total": 0, "added": 0, "skipped": 0, "errors": 0}

    self.update_state(
        state="PROGRESS",
        meta={"stage": "scanning", "current": 0, "total": total, "file": ""},
    )

    # --- 2. Ensure Qdrant collection ---
    model = get_embedding_model()
    store = get_vector_store()
    store.ensure_collection(model.dim)

    added = skipped = errors = 0
    db = SessionLocal()

    try:
        for idx, file_path in enumerate(files, start=1):
            self.update_state(
                state="PROGRESS",
                meta={
                    "stage": "indexing",
                    "current": idx,
                    "total": total,
                    "file": file_path.name,
                },
            )

            try:
                existing = (
                    db.query(AudioFile)
                    .filter(AudioFile.path == str(file_path.resolve()))
                    .first()
                )

                # --- Metadata + waveform ---
                if existing is None:
                    meta = extract_metadata(file_path)
                    peaks = generate_waveform_peaks(
                        file_path, num_samples=config.database.waveform_samples
                    )
                    audio_file = AudioFile(**meta, waveform_peaks=peaks)
                    db.add(audio_file)
                    db.commit()
                    db.refresh(audio_file)
                    added += 1
                else:
                    audio_file = existing
                    if not reindex and audio_file.embedded:
                        skipped += 1
                        continue

                # --- Embedding ---
                try:
                    vec = model.embed_audio(file_path)
                    payload = {
                        "filename": audio_file.filename,
                        "path": audio_file.path,
                        "duration": audio_file.duration,
                        "title": audio_file.title,
                        "artist": audio_file.artist,
                        "album": audio_file.album,
                    }
                    store.upsert(audio_file.id, vec, payload)
                    audio_file.embedded = True
                    audio_file.embedded_at = datetime.utcnow()
                    audio_file.embed_error = None
                except Exception as embed_exc:
                    logger.error("Embedding failed for %s: %s", file_path, embed_exc)
                    audio_file.embed_error = str(embed_exc)
                    errors += 1

                db.commit()

            except Exception as exc:
                logger.error("Failed to process %s: %s", file_path, exc)
                db.rollback()
                errors += 1

    finally:
        db.close()

    return {
        "total": total,
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
