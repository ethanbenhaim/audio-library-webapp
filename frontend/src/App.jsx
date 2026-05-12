import { useEffect, useRef, useState } from "react";
import { getAbletonStatus, searchByText, searchSimilar } from "./api";
import { stopPreview } from "./previewAudio";
import AudioGrid from "./components/AudioGrid";
import AudioPlayer from "./components/AudioPlayer";
import IngestPanel from "./components/IngestPanel";

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [autoPlay, setAutoPlay] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Semantic / similar search state
  const [searchResults, setSearchResults] = useState(null); // null = browse mode
  const [searchSource, setSearchSource] = useState(null);   // source file for similar search
  const [searchLabel, setSearchLabel] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);

  const [liveConnected, setLiveConnected] = useState(false);
  const textInputRef = useRef(null);
  const playerRef = useRef(null);

  // Poll Ableton Live connection every 3 seconds
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const s = await getAbletonStatus().catch(() => ({ connected: false }));
      if (!cancelled) setLiveConnected(s.connected);
    };
    check();
    const id = setInterval(check, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const handleSelect = (file, { autoPlay: shouldAutoPlay = false } = {}) => {
    stopPreview();
    if (selectedFile?.id === file.id) {
      // Same file — toggle play/pause without remounting the player
      playerRef.current?.playPause();
      return;
    }
    setSelectedFile(file);
    setAutoPlay(shouldAutoPlay);
  };

  const handleIngestComplete = () => {
    setRefreshKey((k) => k + 1);
  };

  const clearSearch = () => {
    setSearchResults(null);
    setSearchSource(null);
    setSearchLabel("");
    setSearchError(null);
  };

  const handleTextSearch = async (e) => {
    e.preventDefault();
    const query = textInputRef.current?.value?.trim();
    if (!query) return;

    setSearchLoading(true);
    setSearchError(null);
    setSearchSource(null);
    try {
      const data = await searchByText(query);
      setSearchResults(data.items);
      setSearchLabel(`"${query}"`);
    } catch (err) {
      setSearchError(err.message);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleFindSimilar = async (file) => {
    setSearchLoading(true);
    setSearchError(null);
    try {
      const data = await searchSimilar(file.id);
      setSearchResults(data.items);
      setSearchSource(data.source);
      setSearchLabel(`similar to "${data.source.title || data.source.filename}"`);
    } catch (err) {
      setSearchError(err.message);
    } finally {
      setSearchLoading(false);
    }
  };

  const isSearchMode = searchResults !== null;

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Audio Library</h1>

        {!showIngest && (
          <form className="semantic-search" onSubmit={handleTextSearch}>
            <input
              ref={textInputRef}
              type="text"
              className="semantic-search__input"
              placeholder="Search by sound description…"
              disabled={searchLoading}
            />
            <button
              type="submit"
              className="btn btn--primary semantic-search__btn"
              disabled={searchLoading}
            >
              {searchLoading ? "…" : "Search"}
            </button>
          </form>
        )}

        <div className="ableton-status" title={liveConnected ? "Ableton Live connected" : "Ableton Live not detected"}>
          <span className={`ableton-status__dot ${liveConnected ? "ableton-status__dot--on" : ""}`} />
          <span className="ableton-status__label">{liveConnected ? "Live Online" : "Live Offline"}</span>
        </div>

        <button
          className="btn btn--secondary"
          onClick={() => { setShowIngest((v) => !v); clearSearch(); }}
        >
          {showIngest ? "← Back to Library" : "+ Ingest Folder"}
        </button>
      </header>

      {searchError && (
        <div className="search-error">{searchError}</div>
      )}

      <main className="app-main">
        {showIngest ? (
          <IngestPanel onComplete={handleIngestComplete} />
        ) : (
          <AudioGrid
            selectedFile={selectedFile}
            onSelect={handleSelect}
            onFindSimilar={handleFindSimilar}
            refreshKey={refreshKey}
            searchResults={searchResults}
            searchSource={searchSource}
            searchLabel={searchLabel}
            onClearSearch={clearSearch}
            liveConnected={liveConnected}
          />
        )}
      </main>

      {selectedFile && !showIngest && (
        <footer className="app-player-bar">
          <AudioPlayer
            ref={playerRef}
            file={selectedFile}
            autoPlay={autoPlay}
            onClose={() => setSelectedFile(null)}
          />
        </footer>
      )}
    </div>
  );
}
