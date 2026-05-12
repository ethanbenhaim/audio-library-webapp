"""
AudioWebApp — Ableton Live Remote Script
Bridges the Audio Web App to Live's Python API for operations that
AbletonOSC doesn't expose (creating tracks, loading samples into Simpler).

Protocol: JSON over UDP
  Listens on  127.0.0.1:11002
  Responds on 127.0.0.1:11003
"""

import json
import os
import queue
import shutil
import socket
import threading
import urllib.parse

import Live


LISTEN_PORT = 11002
RESPOND_PORT = 11003
HOST = "127.0.0.1"


class AudioWebApp:
    def __init__(self, c_instance):
        self._c_instance = c_instance
        self._song = c_instance.song()
        self._running = True
        self._sock = None

        self._main_thread_queue = queue.Queue()

        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def update_display(self):
        # Called by Live on the main thread (~100 ms cadence).
        # Drain any work queued from the UDP background thread.
        try:
            while True:
                fn = self._main_thread_queue.get_nowait()
                try:
                    fn()
                except Exception as e:
                    self._log("queue fn error: {}".format(e))
        except queue.Empty:
            pass

    # ── UDP server ───────────────────────────────────────────────────────────

    def _serve(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((HOST, LISTEN_PORT))
        self._sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
                msg = json.loads(data.decode("utf-8"))
                self._dispatch(msg, addr[0])
            except socket.timeout:
                pass
            except Exception:
                pass

    def _send(self, host: str, payload: dict):
        try:
            data = json.dumps(payload).encode("utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(data, (host, RESPOND_PORT))
        except Exception:
            pass

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def _dispatch(self, msg: dict, host: str):
        cmd = msg.get("cmd", "")

        if cmd == "ping":
            self._send(host, {"cmd": "pong"})

        elif cmd == "add_to_simpler":
            file_path = msg.get("path", "")
            host_cap = host
            self._log("add_to_simpler received: {}".format(file_path))

            def _do():
                self._log("_do executing on main thread")
                try:
                    self._add_to_simpler(file_path, host_cap)
                except Exception as e:
                    self._log("_do exception: {}".format(e))
                    self._send(host_cap, {"cmd": "result", "ok": False, "error": str(e)})

            # Try schedule_message first (runs on Live's main thread immediately),
            # fall back to queue (drained by update_display).
            try:
                self._c_instance.schedule_message(1, _do)
                self._log("dispatched via schedule_message")
            except Exception as e:
                self._log("schedule_message failed: {}, using queue".format(e))
                self._main_thread_queue.put(_do)

    # ── Core: create MIDI track + load audio file as Simpler ────────────────

    def _add_to_simpler(self, file_path: str, host: str):
        """
        1. Copy the audio file into the User Library so Live indexes it.
        2. Create a MIDI track and select it.
        3. Search browser.samples by filename.
        4. If found immediately, load via browser.load_item() — Live auto-creates Simpler.
        5. If not yet indexed, register a full_refresh listener and retry up to 8 times.
        """
        self._log("_add_to_simpler: {}".format(file_path))
        if not file_path or not os.path.isfile(file_path):
            self._log("file not found on disk")
            return

        song = self._song
        app  = Live.Application.get_application()
        browser = app.browser

        # ── 0. Copy to User Library (ensures Live will index it) ─────────
        lib_path = self._copy_to_user_library(file_path)
        filename  = os.path.basename(lib_path)

        # ── 1. Create MIDI track after the currently selected track ──────
        insert_idx = -1  # default: end
        try:
            sel = song.view.selected_track
            tracks = list(song.tracks)
            if sel in tracks:
                insert_idx = tracks.index(sel) + 1
        except Exception:
            pass

        song.create_midi_track(insert_idx)
        # After insertion the new track is at insert_idx (or last if insert_idx == -1)
        track_idx = insert_idx if insert_idx != -1 else len(song.tracks) - 1
        new_track = song.tracks[track_idx]
        new_track.name = os.path.splitext(filename)[0]
        song.view.selected_track = new_track
        self._log("created track {}".format(track_idx))

        # ── 2. Try immediately, then retry via background timer ──────────
        item = self._find_in_samples(browser, filename)
        if item is not None:
            self._log("found immediately, loading")
            browser.load_item(item)
            self._send(host, {"cmd": "result", "ok": True, "track_index": track_idx})
            return

        # Not indexed yet — Live needs a moment to scan the new file.
        # Retry every 500 ms (main-thread-safe via queue) up to 12 times (6 s total).
        self._log("not indexed yet, will retry")
        state = {"attempts": 0}

        def retry():
            state["attempts"] += 1
            self._log("retry #{} for {}".format(state["attempts"], filename))
            found = self._find_in_samples(browser, filename)
            if found is not None:
                self._log("found on retry #{}, loading".format(state["attempts"]))
                browser.load_item(found)
                self._send(host, {"cmd": "result", "ok": True, "track_index": track_idx})
            elif state["attempts"] < 12:
                self._schedule_main(retry, delay=0.5)
            else:
                self._log("gave up after {} retries".format(state["attempts"]))
                try:
                    song.delete_track(track_idx)
                except Exception:
                    pass
                self._send(host, {"cmd": "result", "ok": False,
                                  "error": "File not indexed by Live after 6 s"})

        self._schedule_main(retry, delay=0.5)

    # ── Sample management ────────────────────────────────────────────────────

    def _copy_to_user_library(self, file_path: str) -> str:
        """
        Copy file_path into ~/Music/Ableton/User Library/Samples/Imported/.
        Live continuously monitors the User Library and will index new files,
        making them discoverable via browser.samples.
        Returns the destination path (which may equal src if already there).
        """
        try:
            user_lib = os.path.expanduser(
                "~/Music/Ableton/User Library/Samples/Imported"
            )
            src = os.path.normpath(file_path)
            if src.startswith(os.path.normpath(user_lib) + os.sep) or \
               os.path.normpath(os.path.dirname(src)) == os.path.normpath(user_lib):
                return src  # Already in User Library
            os.makedirs(user_lib, exist_ok=True)
            dest = os.path.join(user_lib, os.path.basename(src))
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
            self._log("copied to user library: {}".format(dest))
            return dest
        except Exception as e:
            self._log("_copy_to_user_library error: {}".format(e))
            return file_path

    # ── Browser filesystem navigation ───────────────────────────────────────

    def _schedule_main(self, fn, delay: float = 0.0):
        """Run fn on Live's main thread after `delay` seconds."""
        def _fire():
            self._main_thread_queue.put(fn)
        t = threading.Timer(delay, _fire)
        t.daemon = True
        t.start()

    def _find_in_samples(self, browser, filename: str):
        """Search browser.samples children by exact filename. Returns the BrowserItem or None."""
        try:
            for item in browser.samples.children:
                if getattr(item, "name", "") == filename:
                    return item
        except Exception as e:
            self._log("_find_in_samples error: {}".format(e))
        return None

    def _find_file_in_browser(self, browser, file_path: str):
        """
        Find a BrowserItem for an absolute file path using two strategies:

        1. Search browser.samples by filename — works for any file Live has indexed
           (files used in any project get indexed automatically).

        2. Navigate browser.user_folders by filesystem path — works for files that
           live under one of the user-added browser folders.
        """
        target = os.path.normpath(file_path)
        target_name = os.path.basename(file_path)
        self._log("find_file: target_name={!r}".format(target_name))

        # ── Strategy 1: search Live's sample index by filename ───────────────
        try:
            for item in browser.samples.children:
                if getattr(item, "name", "") == target_name:
                    self._log("found via browser.samples")
                    return item
        except Exception as e:
            self._log("browser.samples search error: {}".format(e))

        # ── Strategy 2: filesystem navigation through user_folders ───────────
        try:
            for folder in browser.user_folders:
                result = self._descend_to(folder, target)
                if result is not None:
                    self._log("found via user_folders")
                    return result
        except Exception as e:
            self._log("user_folders search error: {}".format(e))

        self._log("file not found in browser")
        return None

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        """
        Convert a browser item URI to an absolute filesystem path, or '' if not applicable.

        userfolder: URIs use '#' as separator between the root folder and relative sub-path:
          userfolder:/root/path#sub/dir  →  /root/path/sub/dir
        """
        if uri.startswith("userfolder:"):
            raw = urllib.parse.unquote(uri[len("userfolder:"):])
            raw = raw.replace("#", "/", 1)
            return os.path.normpath(raw)
        if uri.startswith("file://"):
            return os.path.normpath(urllib.parse.unquote(uri[7:]))
        if uri.startswith("/"):
            return os.path.normpath(uri)
        return ""

    def _descend_to(self, item, target: str):
        """
        Recursively navigate from `item` toward `target` using filesystem URIs.
        Returns the matching BrowserItem or None.
        Only follows userfolder: and file:// paths; skips query: nodes.
        """
        try:
            uri = str(getattr(item, "uri", "") or "")
            item_path = self._uri_to_path(uri)

            if not item_path:
                return None  # query: node — not navigable by filesystem path

            if item_path == target:
                return item

            if target.startswith(item_path + os.sep):
                for child in item.children:
                    result = self._descend_to(child, target)
                    if result is not None:
                        return result
        except Exception:
            pass

        return None

    def _log(self, msg: str):
        try:
            with open("/tmp/audioweb_debug.log", "a") as f:
                f.write(msg + "\n")
        except Exception:
            pass
