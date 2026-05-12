import { useEffect, useRef, useState } from "react";
import { fetchFiles } from "../api";
import AudioCard from "./AudioCard";
import AudioListView from "./AudioListView";

export default function AudioGrid({
  selectedFile,
  onSelect,
  onFindSimilar,
  refreshKey,
  searchResults,
  searchSource,
  searchLabel,
  onClearSearch,
  liveConnected,
}) {
  const [files, setFiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState("grid"); // "grid" | "list"
  const [sortField, setSortField] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  const PAGE_SIZE = 50;
  const isSearchMode = searchResults !== null;

  // Keep a stable ref for keyboard handler so it always sees current values
  const navRef = useRef({});
  navRef.current = { files: null, selected: selectedFile, onSelect };

  useEffect(() => { setPage(1); }, [search, refreshKey]);

  useEffect(() => { setPage(1); }, [search, refreshKey]);

  // When entering search mode, default sort by score descending; reset on exit
  useEffect(() => {
    if (searchResults !== null) {
      setSortField("score");
      setSortDir("desc");
    } else {
      setSortField(null);
      setSortDir("asc");
    }
  }, [searchResults]);

  useEffect(() => {
    if (isSearchMode) return; // external results take over

    let cancelled = false;
    setLoading(true);

    fetchFiles({ page, pageSize: PAGE_SIZE, search })
      .then((data) => {
        if (!cancelled) { setFiles(data.items); setTotal(data.total); }
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [page, search, refreshKey, isSearchMode]);

  const displayFiles = isSearchMode ? searchResults : files;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleSort = (field) => {
    if (sortField === field) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortField(field); setSortDir("asc"); }
  };

  const sortedFiles = (view === "list" && sortField !== null)
    ? [...displayFiles].sort((a, b) => {
        let va = a[sortField] ?? "";
        let vb = b[sortField] ?? "";
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va < vb) return sortDir === "asc" ? -1 : 1;
        if (va > vb) return sortDir === "asc" ? 1 : -1;
        return 0;
      })
    : displayFiles;

  // Update nav ref with the order actually visible on screen
  navRef.current.files = sortedFiles;

  // Keyboard navigation — registered once, reads current state via ref
  useEffect(() => {
    const handler = (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      e.preventDefault();

      const { files: f, selected, onSelect: sel } = navRef.current;
      if (!f?.length) return;

      const cur = f.findIndex((x) => x.id === selected?.id);
      const next = e.key === "ArrowDown"
        ? (cur === -1 ? 0 : Math.min(cur + 1, f.length - 1))
        : (cur === -1 ? 0 : Math.max(cur - 1, 0));

      if (f[next]) {
        sel(f[next], { autoPlay: true });
        requestAnimationFrame(() => {
          document.querySelector(`[data-file-id="${f[next].id}"]`)
            ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="audio-grid-container">
      <div className="audio-grid__toolbar">
        {isSearchMode ? (
          <>
            <span className="search-mode-label">
              {searchResults.length} result{searchResults.length !== 1 ? "s" : ""} — {searchLabel}
            </span>
            <button className="btn btn--secondary btn--sm" onClick={onClearSearch}>
              ✕ Clear
            </button>
          </>
        ) : (
          <>
            <input
              type="search"
              className="search-input"
              placeholder="Filter by filename, title, artist, album…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <span className="audio-grid__count">
              {total} file{total !== 1 ? "s" : ""}
            </span>
          </>
        )}

        <div className="view-toggle">
          <button
            className={`view-toggle__btn${view === "grid" ? " view-toggle__btn--active" : ""}`}
            onClick={() => setView("grid")}
            title="Thumbnail view"
          >
            <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor">
              <rect x="1" y="1" width="6" height="6" rx="1"/>
              <rect x="9" y="1" width="6" height="6" rx="1"/>
              <rect x="1" y="9" width="6" height="6" rx="1"/>
              <rect x="9" y="9" width="6" height="6" rx="1"/>
            </svg>
          </button>
          <button
            className={`view-toggle__btn${view === "list" ? " view-toggle__btn--active" : ""}`}
            onClick={() => setView("list")}
            title="List view"
          >
            <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor">
              <rect x="1" y="2" width="14" height="2" rx="1"/>
              <rect x="1" y="7" width="14" height="2" rx="1"/>
              <rect x="1" y="12" width="14" height="2" rx="1"/>
            </svg>
          </button>
        </div>
      </div>

      {searchSource && (
        <div className="search-source">
          <span className="search-source__label">Query</span>
          <div className="search-source__card">
            <AudioCard
              file={searchSource}
              active={selectedFile?.id === searchSource.id}
              onClick={onSelect}
              onFindSimilar={onFindSimilar}
              liveConnected={liveConnected}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading…</div>
      ) : displayFiles.length === 0 ? (
        <div className="empty-state">
          {isSearchMode
            ? "No results found."
            : search
            ? "No files match your search."
            : "No audio files indexed yet. Use the ingest panel to add a folder."}
        </div>
      ) : view === "list" ? (
        <AudioListView
          files={sortedFiles}
          selectedFile={selectedFile}
          onSelect={onSelect}
          onFindSimilar={onFindSimilar}
          showScore={isSearchMode}
          liveConnected={liveConnected}
          sortField={sortField}
          sortDir={sortDir}
          onSort={handleSort}
        />
      ) : (
        <div className="audio-grid">
          {displayFiles.map((f) => (
            <AudioCard
              key={f.id}
              file={f}
              active={selectedFile?.id === f.id}
              onClick={onSelect}
              onFindSimilar={onFindSimilar}
              score={f.score}
              liveConnected={liveConnected}
            />
          ))}
        </div>
      )}

      {!isSearchMode && totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>← Prev</button>
          <span>{page} / {totalPages}</span>
          <button disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
