import { useEffect, useRef, useState } from "react";
import { pollIngestion, startIngestion } from "../api";

export default function IngestPanel({ onComplete }) {
  const [folderPath, setFolderPath] = useState("");
  const [reindex, setReindex] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const clearPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => clearPoll(), []);

  const startPoll = (id) => {
    clearPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await pollIngestion(id);
        setStatus(s);

        if (s.state === "complete") {
          clearPoll();
          onComplete?.();
        } else if (s.state === "failed") {
          clearPoll();
        }
      } catch (err) {
        console.error(err);
      }
    }, 1000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!folderPath.trim()) return;

    setError(null);
    setStatus(null);
    setTaskId(null);

    try {
      const { task_id } = await startIngestion(folderPath.trim(), reindex);
      setTaskId(task_id);
      setStatus({ state: "queued" });
      startPoll(task_id);
    } catch (err) {
      setError(err.message);
    }
  };

  const isRunning = status?.state === "running" || status?.state === "queued";

  const progressPct =
    status?.state === "running" && status.total > 0
      ? Math.round((status.current / status.total) * 100)
      : null;

  return (
    <div className="ingest-panel">
      <h2 className="ingest-panel__title">Ingest Folder</h2>

      <form onSubmit={handleSubmit} className="ingest-panel__form">
        <input
          type="text"
          className="path-input"
          placeholder="/path/to/audio/folder"
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          disabled={isRunning}
        />

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={reindex}
            onChange={(e) => setReindex(e.target.checked)}
            disabled={isRunning}
          />
          Re-embed already indexed files
        </label>

        <button type="submit" disabled={isRunning || !folderPath.trim()} className="btn btn--primary">
          {isRunning ? "Indexing…" : "Start Ingestion"}
        </button>
      </form>

      {error && <div className="ingest-panel__error">{error}</div>}

      {status && (
        <div className="ingest-panel__status">
          {status.state === "queued" && <p>Queued…</p>}

          {status.state === "running" && (
            <>
              <div className="progress-bar">
                <div
                  className="progress-bar__fill"
                  style={{ width: `${progressPct ?? 0}%` }}
                />
              </div>
              <p className="progress-label">
                {status.current} / {status.total} — {status.file}
              </p>
            </>
          )}

          {status.state === "complete" && (
            <p className="status--success">
              Done — {status.added} added, {status.skipped} skipped, {status.errors} errors
            </p>
          )}

          {status.state === "failed" && (
            <p className="status--error">Failed: {status.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
