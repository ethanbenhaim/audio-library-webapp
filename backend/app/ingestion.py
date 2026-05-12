"""
File scanning, metadata extraction, and waveform peak generation.
No ML dependencies — fast enough to run synchronously per file.
"""

import logging
from pathlib import Path

import librosa
import mutagen
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".wav", ".mp3"}


def scan_folder(folder_path: str) -> list[Path]:
    """Recursively find all supported audio files under folder_path."""
    root = Path(folder_path)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {folder_path}")

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(root.rglob(f"*{ext}"))
        files.extend(root.rglob(f"*{ext.upper()}"))

    return sorted(set(files))


def extract_metadata(file_path: Path) -> dict:
    """
    Extract audio properties and ID3/Vorbis tags from a file.
    Returns a flat dict ready to be stored in AudioFile model.
    """
    meta: dict = {
        "path": str(file_path.resolve()),
        "filename": file_path.name,
        "extension": file_path.suffix.lower(),
        "file_size": file_path.stat().st_size,
        "duration": None,
        "sample_rate": None,
        "channels": None,
        "bit_depth": None,
        "title": None,
        "artist": None,
        "album": None,
        "year": None,
        "genre": None,
        "comment": None,
    }

    # --- Audio properties via soundfile (fast, no decode) ---
    try:
        info = sf.info(str(file_path))
        meta["duration"] = info.duration
        meta["sample_rate"] = info.samplerate
        meta["channels"] = info.channels
        # soundfile exposes subtype like PCM_16, PCM_24, etc.
        subtype = info.subtype or ""
        if "16" in subtype:
            meta["bit_depth"] = 16
        elif "24" in subtype:
            meta["bit_depth"] = 24
        elif "32" in subtype:
            meta["bit_depth"] = 32
    except Exception:
        # Fallback: use mutagen for duration on MP3
        pass

    # --- Tags via mutagen ---
    try:
        mf = mutagen.File(str(file_path), easy=True)
        if mf is not None:
            def _tag(key: str) -> str | None:
                val = mf.get(key)
                return str(val[0]) if val else None

            meta["title"] = _tag("title")
            meta["artist"] = _tag("artist")
            meta["album"] = _tag("album")
            meta["year"] = _tag("date")
            meta["genre"] = _tag("genre")
            meta["comment"] = _tag("comment")

            # Mutagen duration fallback for MP3
            if meta["duration"] is None and hasattr(mf, "info"):
                meta["duration"] = getattr(mf.info, "length", None)
            if meta["sample_rate"] is None and hasattr(mf, "info"):
                meta["sample_rate"] = getattr(mf.info, "sample_rate", None)
            if meta["channels"] is None and hasattr(mf, "info"):
                meta["channels"] = getattr(mf.info, "channels", None)
    except Exception as exc:
        logger.warning("mutagen failed for %s: %s", file_path, exc)

    return meta


def generate_waveform_peaks(file_path: Path, num_samples: int = 200) -> list[float]:
    """
    Load audio, downsample to num_samples amplitude peaks, normalised 0.0–1.0.
    Used for lightweight thumbnail rendering without needing the full audio file.
    """
    try:
        y, _ = librosa.load(str(file_path), sr=None, mono=True, res_type="kaiser_fast")
    except Exception as exc:
        logger.warning("librosa failed to load %s: %s", file_path, exc)
        return []

    if len(y) == 0:
        return []

    # Split into num_samples chunks, take max abs value per chunk
    chunk_size = max(1, len(y) // num_samples)
    peaks = []
    for i in range(num_samples):
        start = i * chunk_size
        end = start + chunk_size
        chunk = y[start:end]
        if len(chunk) == 0:
            break
        peaks.append(float(np.max(np.abs(chunk))))

    # Normalise to 0.0–1.0
    max_val = max(peaks) if peaks else 1.0
    if max_val > 0:
        peaks = [p / max_val for p in peaks]

    return peaks
