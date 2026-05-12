from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..celery_app import celery_app
from ..tasks import ingest_folder

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    folder_path: str
    reindex: bool = False


@router.post("")
def start_ingestion(req: IngestRequest):
    """Kick off a background Celery task to ingest a folder."""
    task = ingest_folder.delay(req.folder_path, req.reindex)
    return {"task_id": task.id, "status": "queued"}


@router.get("/{task_id}")
def get_ingestion_status(task_id: str):
    """Poll the status of a running or completed ingestion task."""
    result = celery_app.AsyncResult(task_id)

    state = result.state
    info = result.info or {}

    if state == "PENDING":
        return {"task_id": task_id, "state": "pending"}

    if state == "PROGRESS":
        return {
            "task_id": task_id,
            "state": "running",
            "stage": info.get("stage"),
            "current": info.get("current", 0),
            "total": info.get("total", 0),
            "file": info.get("file", ""),
        }

    if state == "SUCCESS":
        return {"task_id": task_id, "state": "complete", **info}

    if state == "FAILURE":
        return {
            "task_id": task_id,
            "state": "failed",
            "error": str(info),
        }

    return {"task_id": task_id, "state": state.lower()}
