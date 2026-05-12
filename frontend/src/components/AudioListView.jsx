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


function SortIcon({ field, sortField, sortDir }) {
  if (sortField !== field) return <span className="sort-icon sort-icon--idle">↕</span>;
  return <span className="sort-icon">{sortDir === "asc" ? "↑" : "↓"}</span>;
}


function ListRow({ file, active, onClick, onFindSimilar, showScore, liveConnected }) {
  const hoverTimer = useRef(null);
  const [adding, setAdding] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);

  const displayName = file.title || file.filename;
  const artist = [file.artist, file.album].filter(Boolean).join(" — ");

  const handleMouseEnter = () => {
    hoverTimer.current = setTimeout(() => {
      playPreview(audioUrl(file.id));
    }, 300);
  };

  const handleMouseLeave = () => {
    clearTimeout(hoverTimer.current);
    stopPreview();
  };

  const handleAdd = async (e) => {
    e.stopPropagation();
    if (!liveConnected || adding) return;
    setAdding(true);
    try {
      await addToSimpler(file.id);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch {
      setError(true);
      setTimeout(() => setError(false), 2000);
    } finally {
      setAdding(false);
    }
  };

  return (
    <tr
      className={`audio-list__row${active ? " audio-list__row--active" : ""}`}
      data-file-id={file.id}
      onClick={() => onClick(file, { autoPlay: true })}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Score (search mode only) — first column */}
      {showScore && (
        <td className="audio-list__cell-score">
          {file.score != null ? (
            <div className="score-cell">
              <span className="score-cell__pct">{(file.score * 100).toFixed(0)}%</span>
              <div className="score-bar">
                <div
                  className="score-bar__fill"
                  style={{
                    width: `${(file.score * 100).toFixed(1)}%`,
                    background: `hsl(${(Math.pow(file.score, 0.5) * 120).toFixed(1)}, 72%, 42%)`,
                  }}
                />
              </div>
            </div>
          ) : "—"}
        </td>
      )}

      {/* Waveform mini */}
      <td className="audio-list__cell-wave">
        <WaveformThumbnail peaks={file.waveform_peaks || []} active={active} width={56} height={22} />
      </td>

      {/* Name + artist */}
      <td className="audio-list__cell-name">
        <span className="audio-list__name">{displayName}</span>
        {artist && <span className="audio-list__artist">{artist}</span>}
      </td>

      {/* Actions — right of name, always visible */}
      <td className="audio-list__cell-actions" onClick={(e) => e.stopPropagation()}>
        {file.embedded && (
          <button
            className="list-action-btn"
            title="Find similar sounds"
            onClick={(e) => { e.stopPropagation(); onFindSimilar?.(file); }}
          >
            <svg viewBox="0 -2 20 20" width="16" height="16" fill="currentColor">
              <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <line x1="12" y1="12" x2="17" y2="17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <line x1="8" y1="5" x2="8" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}
        <button
          className={`list-action-btn list-add-btn${!liveConnected ? " list-add-btn--disabled" : ""}${success ? " list-add-btn--success" : ""}${error ? " list-add-btn--error" : ""}`}
          title={liveConnected ? "Add to new track in Ableton Live" : "Ableton Live not connected"}
          disabled={!liveConnected || adding}
          onClick={handleAdd}
        >
          {adding ? "…" : success ? "✓" : error ? "✕" : "+"}
        </button>
      </td>

      {/* Duration */}
      <td className="audio-list__cell-num">{formatDuration(file.duration)}</td>

      {/* Type */}
      <td className="audio-list__cell-num">
        {file.extension?.replace(".", "").toUpperCase() || "—"}
      </td>

      {/* Size */}
      <td className="audio-list__cell-num">{formatSize(file.file_size) || "—"}</td>
    </tr>
  );
}

export default function AudioListView({ files, selectedFile, onSelect, onFindSimilar, showScore, liveConnected, sortField = null, sortDir = "asc", onSort }) {
  const col = (field, label, cls = "") => (
    <th className={`audio-list__th ${cls}`} onClick={() => onSort?.(field)}>
      {label} <SortIcon field={field} sortField={sortField} sortDir={sortDir} />
    </th>
  );

  return (
    <table className="audio-list">
      <thead>
        <tr>
          {showScore && col("score", "Accuracy", "audio-list__th--score")}
          <th className="audio-list__th audio-list__th--wave" />
          {col("filename", "Name", "audio-list__th--name")}
          <th className="audio-list__th audio-list__th--actions" />
          {col("duration", "Duration", "audio-list__th--num")}
          {col("extension", "Type", "audio-list__th--num")}
          {col("file_size", "Size", "audio-list__th--num")}
        </tr>
      </thead>
      <tbody>
        {files.map((f) => (
          <ListRow
            key={f.id}
            file={f}
            active={selectedFile?.id === f.id}
            onClick={onSelect}
            onFindSimilar={onFindSimilar}
            showScore={showScore}
            liveConnected={liveConnected}
          />
        ))}
      </tbody>
    </table>
  );
}
