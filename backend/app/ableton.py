"""
Ableton Live integration layer.

Two communication channels:
  1. AbletonOSC Remote Script  (general control) — OSC on port 11000/11001
  2. AudioWebApp Remote Script (Simpler loading) — JSON/UDP on port 11002/11003
"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any

from pythonosc import dispatcher as osc_dispatcher
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient

import logging

logger = logging.getLogger(__name__)

# ── AbletonOSC (general control) ─────────────────────────────────────────────

ABLETONOSC_SEND_PORT = 11000   # we send to Live
ABLETONOSC_RECV_PORT = 11001   # we receive from Live
AUDIOWEBAPP_SEND_PORT = 11002  # we send to AudioWebApp script
AUDIOWEBAPP_RECV_PORT = 11003  # we receive from AudioWebApp script
HOST = "127.0.0.1"


class AbletonOSCClient:
    """
    Thin OSC client for AbletonOSC.
    Send a message and optionally wait for a reply on the same address.
    """

    def __init__(self):
        self._client = SimpleUDPClient(HOST, ABLETONOSC_SEND_PORT)
        self._responses: dict[str, Any] = {}
        self._lock = threading.Lock()

        disp = osc_dispatcher.Dispatcher()
        disp.set_default_handler(self._on_message)

        self._server = osc_server.ThreadingOSCUDPServer(
            (HOST, ABLETONOSC_RECV_PORT), disp
        )
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def _on_message(self, address: str, *args):
        with self._lock:
            self._responses[address] = args

    def send(self, address: str, *args):
        self._client.send_message(address, list(args))

    def query(self, address: str, *args, timeout: float = 1.5) -> tuple | None:
        with self._lock:
            self._responses.pop(address, None)
        self.send(address, *args)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if address in self._responses:
                    return self._responses[address]
            time.sleep(0.01)
        return None

    def is_alive(self, timeout: float = 0.5) -> bool:
        return self.query("/live/song/get/tempo", timeout=timeout) is not None


# ── AudioWebApp JSON/UDP client ───────────────────────────────────────────────

class AudioWebAppClient:
    """
    JSON-over-UDP client for the AudioWebApp Remote Script.
    """

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((HOST, AUDIOWEBAPP_RECV_PORT))
        self._sock.settimeout(0.05)

        self._responses: dict[str, Any] = {}
        self._lock = threading.Lock()

        t = threading.Thread(target=self._listen, daemon=True)
        t.start()

    def _listen(self):
        while True:
            try:
                data, _ = self._sock.recvfrom(4096)
                msg = json.loads(data.decode("utf-8"))
                cmd = msg.get("cmd", "")
                with self._lock:
                    self._responses[cmd] = msg
            except socket.timeout:
                pass
            except Exception:
                pass

    def send(self, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(data, (HOST, AUDIOWEBAPP_SEND_PORT))

    def request(self, payload: dict, reply_cmd: str, timeout: float = 2.0) -> dict | None:
        with self._lock:
            self._responses.pop(reply_cmd, None)
        self.send(payload)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if reply_cmd in self._responses:
                    return self._responses.pop(reply_cmd)
            time.sleep(0.01)
        return None

    def ping(self, timeout: float = 0.5) -> bool:
        resp = self.request({"cmd": "ping"}, "pong", timeout=timeout)
        return resp is not None


# ── Unified Ableton facade ────────────────────────────────────────────────────

class AbletonBridge:
    """
    Single entry point for all Ableton Live control.

    General control (transport, tracks, clips, devices, mixer) is routed
    through AbletonOSC on port 11000.

    Track-creation with Simpler loading is routed through the custom
    AudioWebApp Remote Script on port 11002.
    """

    def __init__(self):
        self._osc = AbletonOSCClient()
        self._webapp = AudioWebAppClient()

    # ── Connection ───────────────────────────────────────────────────────────

    def status(self) -> dict:
        osc_ok = self._osc.is_alive()
        webapp_ok = self._webapp.ping()
        return {
            "connected": webapp_ok,
            "abletonosc": osc_ok,
            "audiowebapp": webapp_ok,
        }

    # ── Transport ────────────────────────────────────────────────────────────

    def play(self):             self._osc.send("/live/song/start_playing")
    def stop(self):             self._osc.send("/live/song/stop_playing")
    def continue_playing(self): self._osc.send("/live/song/continue_playing")
    def tap_tempo(self):        self._osc.send("/live/song/tap_tempo")
    def undo(self):             self._osc.send("/live/song/undo")
    def redo(self):             self._osc.send("/live/song/redo")

    def get_tempo(self) -> float | None:
        r = self._osc.query("/live/song/get/tempo")
        return float(r[0]) if r else None

    def set_tempo(self, bpm: float):
        self._osc.send("/live/song/set/tempo", float(bpm))

    def get_time(self) -> float | None:
        r = self._osc.query("/live/song/get/current_song_time")
        return float(r[0]) if r else None

    def get_is_playing(self) -> bool | None:
        r = self._osc.query("/live/song/get/is_playing")
        return bool(r[0]) if r else None

    def get_time_signature(self) -> dict | None:
        num = self._osc.query("/live/song/get/signature_numerator")
        den = self._osc.query("/live/song/get/signature_denominator")
        if num and den:
            return {"numerator": int(num[0]), "denominator": int(den[0])}
        return None

    def set_time_signature(self, numerator: int, denominator: int):
        self._osc.send("/live/song/set/signature_numerator", numerator)
        self._osc.send("/live/song/set/signature_denominator", denominator)

    def set_record_mode(self, enabled: bool):
        self._osc.send("/live/song/set/record_mode", int(enabled))

    def set_overdub(self, enabled: bool):
        self._osc.send("/live/song/set/overdub", int(enabled))

    def set_metronome(self, enabled: bool):
        self._osc.send("/live/song/set/metronome", int(enabled))

    # ── Tracks ───────────────────────────────────────────────────────────────

    def get_num_tracks(self) -> int | None:
        r = self._osc.query("/live/song/get/num_tracks")
        return int(r[0]) if r else None

    def create_midi_track(self, index: int = -1):
        self._osc.send("/live/song/create_midi_track", index)

    def create_audio_track(self, index: int = -1):
        self._osc.send("/live/song/create_audio_track", index)

    def create_return_track(self):
        self._osc.send("/live/song/create_return_track")

    def delete_track(self, track_idx: int):
        self._osc.send("/live/song/delete_track", track_idx)

    def duplicate_track(self, track_idx: int):
        self._osc.send("/live/song/duplicate_track", track_idx)

    def set_track_name(self, track_idx: int, name: str):
        self._osc.send("/live/track/set/name", track_idx, name)

    def get_track_name(self, track_idx: int) -> str | None:
        r = self._osc.query("/live/track/get/name", track_idx)
        return str(r[0]) if r else None

    def set_track_volume(self, track_idx: int, volume: float):
        """volume: 0.0–1.0 (0.85 ≈ 0 dB)"""
        self._osc.send("/live/track/set/volume", track_idx, float(volume))

    def set_track_panning(self, track_idx: int, pan: float):
        """pan: -1.0 (L) to 1.0 (R)"""
        self._osc.send("/live/track/set/panning", track_idx, float(pan))

    def set_track_mute(self, track_idx: int, muted: bool):
        self._osc.send("/live/track/set/mute", track_idx, int(muted))

    def set_track_solo(self, track_idx: int, solo: bool):
        self._osc.send("/live/track/set/solo", track_idx, int(solo))

    def set_track_arm(self, track_idx: int, armed: bool):
        self._osc.send("/live/track/set/arm", track_idx, int(armed))

    def set_track_color(self, track_idx: int, color: int):
        self._osc.send("/live/track/set/color", track_idx, color)

    def get_track_devices(self, track_idx: int) -> list[dict] | None:
        names = self._osc.query("/live/track/get/devices/name", track_idx)
        types = self._osc.query("/live/track/get/devices/class_name", track_idx)
        if names is None:
            return None
        result = []
        for i, name in enumerate(names):
            result.append({
                "index": i,
                "name": name,
                "class_name": types[i] if types and i < len(types) else None,
            })
        return result

    # ── Devices ──────────────────────────────────────────────────────────────

    def get_device_parameters(self, track_idx: int, device_idx: int) -> list[dict] | None:
        names = self._osc.query("/live/device/get/parameters/name", track_idx, device_idx)
        values = self._osc.query("/live/device/get/parameters/value", track_idx, device_idx)
        if names is None:
            return None
        result = []
        for i, name in enumerate(names):
            result.append({
                "index": i,
                "name": name,
                "value": values[i] if values and i < len(values) else None,
            })
        return result

    def set_device_parameter(self, track_idx: int, device_idx: int, param_idx: int, value: float):
        self._osc.send("/live/device/set/parameter/value",
                       track_idx, device_idx, param_idx, float(value))

    def delete_device(self, track_idx: int, device_idx: int):
        self._osc.send("/live/track/delete_device", track_idx, device_idx)

    # ── Clips & scenes ───────────────────────────────────────────────────────

    def fire_clip(self, track_idx: int, clip_idx: int):
        self._osc.send("/live/clip_slot/fire", track_idx, clip_idx)

    def stop_clip(self, track_idx: int, clip_idx: int):
        self._osc.send("/live/clip_slot/stop", track_idx, clip_idx)

    def get_num_scenes(self) -> int | None:
        r = self._osc.query("/live/song/get/num_scenes")
        return int(r[0]) if r else None

    def create_scene(self, index: int = -1):
        self._osc.send("/live/song/create_scene", index)

    def delete_scene(self, index: int):
        self._osc.send("/live/song/delete_scene", index)

    def fire_scene(self, index: int):
        self._osc.send("/live/scene/fire", index)

    def get_scene_name(self, index: int) -> str | None:
        r = self._osc.query("/live/scene/get/name", index)
        return str(r[0]) if r else None

    def set_scene_name(self, index: int, name: str):
        self._osc.send("/live/scene/set/name", index, name)

    # ── Master & cue ─────────────────────────────────────────────────────────

    def get_master_volume(self) -> float | None:
        r = self._osc.query("/live/master_track/get/volume")
        return float(r[0]) if r else None

    def set_master_volume(self, volume: float):
        self._osc.send("/live/master_track/set/volume", float(volume))

    def set_cue_volume(self, volume: float):
        self._osc.send("/live/master_track/set/cue_volume", float(volume))

    # ── Custom: add audio file to new MIDI track via Simpler ─────────────────

    def add_to_simpler(self, file_path: str) -> dict:
        """
        Create a new MIDI track and load file_path into Simpler.
        Routes through the AudioWebApp Remote Script.
        """
        resp = self._webapp.request(
            {"cmd": "add_to_simpler", "path": file_path},
            reply_cmd="result",
            timeout=10.0,
        )
        if resp is None:
            return {"ok": False, "error": "AudioWebApp Remote Script not responding"}
        return resp


# ── Module-level singleton ────────────────────────────────────────────────────

_bridge: AbletonBridge | None = None


def get_bridge() -> AbletonBridge:
    global _bridge
    if _bridge is None:
        _bridge = AbletonBridge()
    return _bridge
