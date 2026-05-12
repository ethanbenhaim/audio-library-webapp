import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { audioUrl } from "../api";
import { setPlayerPlaying, stopPreview } from "../previewAudio";

const AudioPlayer = forwardRef(function AudioPlayer({ file, onClose, autoPlay = false }, ref) {
  const containerRef = useRef(null);
  const wsRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(file.duration || 0);
  const [volume, setVolume] = useState(0.8);

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#6b7280",
      progressColor: "#60a5fa",
      cursorColor: "#93c5fd",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
      url: audioUrl(file.id),
    });

    ws.on("ready", () => {
      setDuration(ws.getDuration());
      ws.setVolume(volume);
      if (autoPlay) ws.play();
    });

    ws.on("audioprocess", () => setCurrentTime(ws.getCurrentTime()));
    ws.on("seeking", () => setCurrentTime(ws.getCurrentTime()));
    ws.on("play", () => { setPlaying(true); setPlayerPlaying(true); stopPreview(); });
    ws.on("pause", () => { setPlaying(false); setPlayerPlaying(false); });
    ws.on("finish", () => { setPlaying(false); setPlayerPlaying(false); });

    wsRef.current = ws;

    return () => {
      ws.destroy();
      wsRef.current = null;
      setPlayerPlaying(false);
    };
  }, [file.id]);

  // Spacebar → play/pause (skip when typing in inputs)
  useEffect(() => {
    const handler = (e) => {
      if (e.code !== "Space") return;
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
      e.preventDefault();
      wsRef.current?.playPause();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  useImperativeHandle(ref, () => ({
    playPause: () => wsRef.current?.playPause(),
  }));

  const togglePlay = () => wsRef.current?.playPause();

  const handleVolumeChange = (e) => {
    const v = parseFloat(e.target.value);
    setVolume(v);
    wsRef.current?.setVolume(v);
  };

  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const displayName = file.title || file.filename;
  const sub = [file.artist, file.album].filter(Boolean).join(" — ");

  return (
    <div className="player">
      <div className="player__info">
        <div className="player__name">{displayName}</div>
        {sub && <div className="player__sub">{sub}</div>}
      </div>

      <div className="player__waveform" ref={containerRef} />

      <div className="player__controls">
        <button className="player__play-btn" onClick={togglePlay} title={playing ? "Pause" : "Play"}>
          {playing ? (
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
              <polygon points="5,3 19,12 5,21" />
            </svg>
          )}
        </button>

        <span className="player__time">
          {fmt(currentTime)} / {fmt(duration)}
        </span>

        <div className="player__volume">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
          </svg>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={volume}
            onChange={handleVolumeChange}
            className="volume-slider"
          />
        </div>

        <button className="player__close-btn" onClick={onClose} title="Close">
          ✕
        </button>
      </div>
    </div>
  );
});

export default AudioPlayer;
