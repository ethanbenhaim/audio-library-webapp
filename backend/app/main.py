from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import ableton, files, ingest, search

# Ensure tables exist on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Audio Webapp", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(ableton.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
