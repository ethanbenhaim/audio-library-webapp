const BASE = "/api";

export async function fetchFiles({ page = 1, pageSize = 50, search = "" } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (search) params.set("search", search);
  const res = await fetch(`${BASE}/files?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchFile(id) {
  const res = await fetch(`${BASE}/files/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function audioUrl(id) {
  return `${BASE}/files/${id}/audio`;
}

export async function startIngestion(folderPath, reindex = false) {
  const res = await fetch(`${BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_path: folderPath, reindex }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function pollIngestion(taskId) {
  const res = await fetch(`${BASE}/ingest/${taskId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function searchByText(query, limit = 20) {
  const res = await fetch(`${BASE}/search/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function searchSimilar(fileId, limit = 20) {
  const res = await fetch(`${BASE}/files/${fileId}/similar?limit=${limit}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Ableton ──────────────────────────────────────────────────────────────────

export async function getAbletonStatus() {
  const res = await fetch(`${BASE}/ableton/status`);
  if (!res.ok) return { connected: false };
  return res.json();
}

export async function addToSimpler(fileId) {
  const res = await fetch(`${BASE}/ableton/add_to_simpler/${fileId}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
