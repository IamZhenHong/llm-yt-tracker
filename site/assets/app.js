const state = {
  videos: [],
  graph: { nodes: [], links: [] },
  signatures: {},
  filter: { topic: null, channel: null, text: "" },
  sortBy: "date",
};

async function boot() {
  const [videos, graph, signatures] = await Promise.all([
    fetch("./data/videos.json").then(r => r.json()).catch(() => []),
    fetch("./data/graph.json").then(r => r.json()).catch(() => ({ nodes: [], links: [] })),
    fetch("./data/signatures.json").then(r => r.json()).catch(() => ({})),
  ]);
  state.videos = videos;
  state.graph = graph;
  state.signatures = signatures;

  readFiltersFromUrl();
  renderTimestamp();
  renderGraph();
  renderSignatures();
  renderClaims();
  renderVideos();
  wireFilters();
}

function readFiltersFromUrl() {
  const p = new URLSearchParams(window.location.search);
  if (p.get("topic")) state.filter.topic = p.get("topic");
  if (p.get("channel")) state.filter.channel = p.get("channel");
  if (p.get("q")) state.filter.text = p.get("q");
}

function writeFiltersToUrl() {
  const p = new URLSearchParams();
  if (state.filter.topic) p.set("topic", state.filter.topic);
  if (state.filter.channel) p.set("channel", state.filter.channel);
  if (state.filter.text) p.set("q", state.filter.text);
  const qs = p.toString();
  const newUrl = qs ? `?${qs}` : window.location.pathname;
  window.history.replaceState({}, "", newUrl);
}

function renderTimestamp() {
  if (!state.videos.length) {
    document.getElementById("last-updated").textContent = "No data yet.";
    return;
  }
  const newest = state.videos.reduce((a, b) =>
    a.processed_at > b.processed_at ? a : b);
  document.getElementById("last-updated").textContent = `Last updated: ${newest.processed_at}`;
}

// Stubs (implemented in later tasks)
function renderGraph() { /* Task 13 */ }
function renderSignatures() { /* Task 14 */ }
function renderClaims() { /* Task 15 */ }
function renderVideos() { /* Task 16 */ }
function wireFilters() { /* Task 16 */ }

boot();
