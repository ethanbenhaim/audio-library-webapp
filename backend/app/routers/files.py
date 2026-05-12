from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AudioFile
from ..vector_store import get_vector_store

router = APIRouter(prefix="/files", tags=["files"])


def _file_dict(f: AudioFile) -> dict:
    return {
        "id": f.id,
        "filename": f.filename,
        "path": f.path,
        "extension": f.extension,
        "file_size": f.file_size,
        "duration": f.duration,
        "sample_rate": f.sample_rate,
        "channels": f.channels,
        "bit_depth": f.bit_depth,
        "title": f.title,
        "artist": f.artist,
        "album": f.album,
        "year": f.year,
        "genre": f.genre,
        "waveform_peaks": f.waveform_peaks,
        "embedded": f.embedded,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.get("")
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(""),
    db: Session = Depends(get_db),
):
    """List audio files with optional filename/metadata search and pagination."""
    q = db.query(AudioFile)

    if search:
        like = f"%{search}%"
        q = q.filter(
            AudioFile.filename.ilike(like)
            | AudioFile.title.ilike(like)
            | AudioFile.artist.ilike(like)
            | AudioFile.album.ilike(like)
        )

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_file_dict(f) for f in items],
    }


@router.get("/{file_id}")
def get_file(file_id: int, db: Session = Depends(get_db)):
    f = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if f is None:
        raise HTTPException(status_code=404, detail="File not found")
    return _file_dict(f)


@router.get("/{file_id}/similar")
def find_similar(
    file_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return files whose audio embeddings are most similar to the given file."""
    af = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if af is None:
        raise HTTPException(status_code=404, detail="File not found")
    if not af.embedded:
        raise HTTPException(status_code=422, detail="File has not been embedded yet")

    store = get_vector_store()
    vec = store.retrieve_vector(file_id)
    if vec is None:
        raise HTTPException(status_code=404, detail="Embedding not found in vector store")

    results = store.search(vec, limit=limit + 1)
    items = []
    for r in results:
        if r["id"] == file_id:
            continue
        f = db.query(AudioFile).filter(AudioFile.id == r["id"]).first()
        if f:
            items.append({**_file_dict(f), "score": round(r["score"], 4)})

    return {"source": _file_dict(af), "items": items[:limit]}


@router.get("/{file_id}/audio")
def stream_audio(file_id: int, db: Session = Depends(get_db)):
    """Stream the raw audio file (supports byte-range requests for seeking)."""
    f = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if f is None:
        raise HTTPException(status_code=404, detail="File not found")

    path = Path(f.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    media_type = "audio/mpeg" if f.extension == ".mp3" else "audio/wav"
    return FileResponse(str(path), media_type=media_type)
