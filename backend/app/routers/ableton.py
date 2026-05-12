from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ableton import get_bridge
from ..database import get_db
from ..models import AudioFile

router = APIRouter(prefix="/ableton", tags=["ableton"])


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    """Check whether AbletonOSC and AudioWebApp remote scripts are responding."""
    return get_bridge().status()


# ── Transport ─────────────────────────────────────────────────────────────────

@router.post("/transport/play")
def play():
    get_bridge().play()
    return {"ok": True}

@router.post("/transport/stop")
def stop():
    get_bridge().stop()
    return {"ok": True}

@router.post("/transport/continue")
def continue_playing():
    get_bridge().continue_playing()
    return {"ok": True}

@router.post("/transport/tap_tempo")
def tap_tempo():
    get_bridge().tap_tempo()
    return {"ok": True}

@router.post("/transport/undo")
def undo():
    get_bridge().undo()
    return {"ok": True}

@router.post("/transport/redo")
def redo():
    get_bridge().redo()
    return {"ok": True}

@router.get("/transport")
def get_transport():
    b = get_bridge()
    return {
        "tempo": b.get_tempo(),
        "is_playing": b.get_is_playing(),
        "time": b.get_time(),
        "time_signature": b.get_time_signature(),
    }


class TempoBody(BaseModel):
    bpm: float

@router.post("/transport/tempo")
def set_tempo(body: TempoBody):
    get_bridge().set_tempo(body.bpm)
    return {"ok": True}


class TimeSignatureBody(BaseModel):
    numerator: int
    denominator: int

@router.post("/transport/time_signature")
def set_time_signature(body: TimeSignatureBody):
    get_bridge().set_time_signature(body.numerator, body.denominator)
    return {"ok": True}


class BoolBody(BaseModel):
    enabled: bool

@router.post("/transport/record")
def set_record(body: BoolBody):
    get_bridge().set_record_mode(body.enabled)
    return {"ok": True}

@router.post("/transport/overdub")
def set_overdub(body: BoolBody):
    get_bridge().set_overdub(body.enabled)
    return {"ok": True}

@router.post("/transport/metronome")
def set_metronome(body: BoolBody):
    get_bridge().set_metronome(body.enabled)
    return {"ok": True}


# ── Tracks ────────────────────────────────────────────────────────────────────

@router.get("/tracks/count")
def get_track_count():
    return {"count": get_bridge().get_num_tracks()}


class CreateTrackBody(BaseModel):
    index: int = -1

@router.post("/tracks/midi")
def create_midi_track(body: CreateTrackBody):
    get_bridge().create_midi_track(body.index)
    return {"ok": True}

@router.post("/tracks/audio")
def create_audio_track(body: CreateTrackBody):
    get_bridge().create_audio_track(body.index)
    return {"ok": True}

@router.post("/tracks/return")
def create_return_track():
    get_bridge().create_return_track()
    return {"ok": True}

@router.delete("/tracks/{track_idx}")
def delete_track(track_idx: int):
    get_bridge().delete_track(track_idx)
    return {"ok": True}

@router.post("/tracks/{track_idx}/duplicate")
def duplicate_track(track_idx: int):
    get_bridge().duplicate_track(track_idx)
    return {"ok": True}


class TrackNameBody(BaseModel):
    name: str

@router.post("/tracks/{track_idx}/name")
def set_track_name(track_idx: int, body: TrackNameBody):
    get_bridge().set_track_name(track_idx, body.name)
    return {"ok": True}


class VolumeBody(BaseModel):
    volume: float  # 0.0–1.0

@router.post("/tracks/{track_idx}/volume")
def set_track_volume(track_idx: int, body: VolumeBody):
    get_bridge().set_track_volume(track_idx, body.volume)
    return {"ok": True}


class PanBody(BaseModel):
    pan: float  # -1.0 to 1.0

@router.post("/tracks/{track_idx}/pan")
def set_track_pan(track_idx: int, body: PanBody):
    get_bridge().set_track_panning(track_idx, body.pan)
    return {"ok": True}

@router.post("/tracks/{track_idx}/mute")
def set_track_mute(track_idx: int, body: BoolBody):
    get_bridge().set_track_mute(track_idx, body.enabled)
    return {"ok": True}

@router.post("/tracks/{track_idx}/solo")
def set_track_solo(track_idx: int, body: BoolBody):
    get_bridge().set_track_solo(track_idx, body.enabled)
    return {"ok": True}

@router.post("/tracks/{track_idx}/arm")
def set_track_arm(track_idx: int, body: BoolBody):
    get_bridge().set_track_arm(track_idx, body.enabled)
    return {"ok": True}

@router.get("/tracks/{track_idx}/devices")
def get_track_devices(track_idx: int):
    devices = get_bridge().get_track_devices(track_idx)
    if devices is None:
        raise HTTPException(status_code=503, detail="Live not responding")
    return {"devices": devices}


# ── Devices ───────────────────────────────────────────────────────────────────

@router.get("/tracks/{track_idx}/devices/{device_idx}/parameters")
def get_device_parameters(track_idx: int, device_idx: int):
    params = get_bridge().get_device_parameters(track_idx, device_idx)
    if params is None:
        raise HTTPException(status_code=503, detail="Live not responding")
    return {"parameters": params}


class SetParamBody(BaseModel):
    value: float

@router.post("/tracks/{track_idx}/devices/{device_idx}/parameters/{param_idx}")
def set_device_parameter(track_idx: int, device_idx: int, param_idx: int, body: SetParamBody):
    get_bridge().set_device_parameter(track_idx, device_idx, param_idx, body.value)
    return {"ok": True}

@router.delete("/tracks/{track_idx}/devices/{device_idx}")
def delete_device(track_idx: int, device_idx: int):
    get_bridge().delete_device(track_idx, device_idx)
    return {"ok": True}


# ── Clips & scenes ────────────────────────────────────────────────────────────

class ClipBody(BaseModel):
    track_idx: int
    clip_idx: int

@router.post("/clips/fire")
def fire_clip(body: ClipBody):
    get_bridge().fire_clip(body.track_idx, body.clip_idx)
    return {"ok": True}

@router.post("/clips/stop")
def stop_clip(body: ClipBody):
    get_bridge().stop_clip(body.track_idx, body.clip_idx)
    return {"ok": True}

@router.get("/scenes/count")
def get_scene_count():
    return {"count": get_bridge().get_num_scenes()}

@router.post("/scenes/create")
def create_scene(body: CreateTrackBody):
    get_bridge().create_scene(body.index)
    return {"ok": True}

@router.post("/scenes/{scene_idx}/fire")
def fire_scene(scene_idx: int):
    get_bridge().fire_scene(scene_idx)
    return {"ok": True}

@router.delete("/scenes/{scene_idx}")
def delete_scene(scene_idx: int):
    get_bridge().delete_scene(scene_idx)
    return {"ok": True}


# ── Master ────────────────────────────────────────────────────────────────────

@router.get("/master/volume")
def get_master_volume():
    return {"volume": get_bridge().get_master_volume()}

@router.post("/master/volume")
def set_master_volume(body: VolumeBody):
    get_bridge().set_master_volume(body.volume)
    return {"ok": True}

@router.post("/master/cue_volume")
def set_cue_volume(body: VolumeBody):
    get_bridge().set_cue_volume(body.volume)
    return {"ok": True}


# ── Add to Simpler ────────────────────────────────────────────────────────────

@router.post("/add_to_simpler/{file_id}")
def add_to_simpler(file_id: int, db: Session = Depends(get_db)):
    """Create a new MIDI track and load this audio file into Ableton's Simpler device."""
    af = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if af is None:
        raise HTTPException(status_code=404, detail="File not found")

    result = get_bridge().add_to_simpler(af.path)
    if not result.get("ok"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "AudioWebApp Remote Script not responding — is it loaded in Live?"),
        )
    return result
