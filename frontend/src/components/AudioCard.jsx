import { useRef, useState } from "react";
import { addToSimpler, audioUrl } from "../api";
import { playPreview, stopPreview } from "../previewAudio";
import WaveformThumbnail from "./WaveformThumbnail";

function formatDuration(seconds) {
  if (!seconds) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AudioCard({ file, active, onClick, onFindSimilar, score, liveConnected }) {
  const hoverTimer = useRef(null);
  const [addingToTrack, setAddingToTrack] = useState(false);
  const [addSuccess, setAddSuccess] = useState(false);
  const [addError, setAddError] = useState(null);
  const displayName = file.title || file.filename;
  const sub = [file.artist, file.album].filter(Boolean).join(" — ");

  const handleMouseEnter = () => {
    hoverTimer.current = setTimeout(() => {
      playPreview(audioUrl(file.id));
    }, 300);
  };

  const handleMouseLeave = () => {
    clearTimeout(hoverTimer.current);
    stopPreview();
  };

  const handleSimilarClick = (e) => {
    e.stopPropagation();
    onFindSimilar?.(file);
  };

  const handleAddToTrack = async (e) => {
    e.stopPropagation();
    if (!liveConnected || addingToTrack) return;
    setAddingToTrack(true);
    setAddError(null);
    try {
      await addToSimpler(file.id);
      setAddSuccess(true);
      setTimeout(() => setAddSuccess(false), 2000);
    } catch (err) {
      setAddError("Failed");
      setTimeout(() => setAddError(null), 2000);
    } finally {
      setAddingToTrack(false);
    }
  };

  return (
    <div
      className={`audio-card ${active ? "audio-card--active" : ""}`}
      data-file-id={file.id}
      onClick={() => onClick(file, { autoPlay: true })}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="audio-card__waveform">
        <WaveformThumbnail
          peaks={file.waveform_peaks || []}
          active={active}
          width={180}
          height={48}
        />
        {file.embedded && (
          <button
            className="similar-btn"
            onClick={handleSimilarClick}
            title="Find similar sounds"
          >
            <svg viewBox="0 0 20 20" width="13" height="13" fill="currentColor">
              <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <line x1="12" y1="12" x2="17" y2="17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <line x1="8" y1="5" x2="8" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}
      </div>

      <div className="audio-card__info">
        <div className="audio-card__name" title={file.filename}>{displayName}</div>
        {sub && <div className="audio-card__sub" title={sub}>{sub}</div>}
        <div className="audio-card__meta">
          <span>{formatDuration(file.duration)}</span>
          <span>{file.extension?.replace(".", "").toUpperCase()}</span>
          <span>{formatSize(file.file_size)}</span>
          {score != null && (
            <span className="badge badge--score">{(score * 100).toFixed(0)}%</span>
          )}
          {file.embedded && score == null && (
            <span className="badge badge--embedded">indexed</span>
          )}
        </div>

        <button
          className={`add-to-track-btn ${!liveConnected ? "add-to-track-btn--disabled" : ""} ${addSuccess ? "add-to-track-btn--success" : ""}`}
          onClick={handleAddToTrack}
          disabled={!liveConnected || addingToTrack}
          title={liveConnected ? "Add to new track in Ableton Live" : "Ableton Live not connected"}
        >
          {addingToTrack ? "Adding…" : addError ? addError : addSuccess ? "✓ Added to track" : "+ Add to new track"}
        </button>
      </div>
    </div>
  );
}
