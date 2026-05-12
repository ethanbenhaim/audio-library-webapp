from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import SessionLocal
from ..models import AudioFile
from ..routers.files import _file_dict

router = APIRouter(prefix="/search", tags=["search"])


class TextSearchRequest(BaseModel):
    query: str
    limit: int = 20


@router.post("/text")
def text_search(req: TextSearchRequest):
    """Embed a text query with CLAP and return the closest audio files by cosine similarity."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        from ..embeddings import get_embedding_model
        model = get_embedding_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding model unavailable: {exc}")

    vec = model.embed_text(req.query.strip())

    from ..vector_store import get_vector_store
    store = get_vector_store()
    results = store.search(vec, limit=req.limit)

    db = SessionLocal()
    try:
        items = []
        for r in results:
            f = db.query(AudioFile).filter(AudioFile.id == r["id"]).first()
            if f:
                items.append({**_file_dict(f), "score": round(r["score"], 4)})
        return {"query": req.query, "items": items}
    finally:
        db.close()
