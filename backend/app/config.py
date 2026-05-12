import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass
class EmbeddingConfig:
    model_type: str = "clap"
    model_id: str = "laion/larger_clap_general"
    device: str = "cpu"
    batch_size: int = 4


@dataclass
class DatabaseConfig:
    sqlite_path: str = "../data/audio.db"
    waveform_samples: int = 200


@dataclass
class QdrantConfig:
    mode: str = "local"           # "local" (embedded) or "server"
    local_path: str = "../data/qdrant"
    host: str = "localhost"
    port: int = 6333
    collection: str = "audio_files"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class CeleryConfig:
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"


@dataclass
class AppConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    celery: CeleryConfig = field(default_factory=CeleryConfig)


def load_config(path: Path = _CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with open(path) as f:
        raw = yaml.safe_load(f)

    cfg = AppConfig()

    if "embedding" in raw:
        e = raw["embedding"]
        cfg.embedding = EmbeddingConfig(
            model_type=e.get("model_type", cfg.embedding.model_type),
            model_id=e.get("model_id", cfg.embedding.model_id),
            device=e.get("device", cfg.embedding.device),
            batch_size=e.get("batch_size", cfg.embedding.batch_size),
        )

    if "database" in raw:
        d = raw["database"]
        cfg.database = DatabaseConfig(
            sqlite_path=d.get("sqlite_path", cfg.database.sqlite_path),
            waveform_samples=d.get("waveform_samples", cfg.database.waveform_samples),
        )

    if "qdrant" in raw:
        q = raw["qdrant"]
        cfg.qdrant = QdrantConfig(
            mode=q.get("mode", cfg.qdrant.mode),
            local_path=q.get("local_path", cfg.qdrant.local_path),
            host=q.get("host", cfg.qdrant.host),
            port=q.get("port", cfg.qdrant.port),
            collection=q.get("collection", cfg.qdrant.collection),
        )

    if "server" in raw:
        s = raw["server"]
        cfg.server = ServerConfig(
            host=s.get("host", cfg.server.host),
            port=s.get("port", cfg.server.port),
        )

    if "celery" in raw:
        c = raw["celery"]
        cfg.celery = CeleryConfig(
            broker_url=c.get("broker_url", cfg.celery.broker_url),
            result_backend=c.get("result_backend", cfg.celery.result_backend),
        )

    return cfg


# Module-level singleton
config = load_config()
