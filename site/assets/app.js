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
function renderGraph() {
  const container = document.getElementById("graph");
  container.innerHTML = "";
  if (!state.graph.nodes.length) {
    container.innerHTML = "<p style='padding:16px;color:var(--muted)'>No graph data yet.</p>";
    return;
  }

  const rect = container.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  const svg = d3.select("#graph").append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);

  const channelColors = ["#2a4b7c", "#7a3e3a", "#4b6b3f", "#8a6436", "#5c3e6e", "#3a6a6b", "#8e5d2a", "#3d3a4f"];
  const channelIds = state.graph.nodes.filter(n => n.type === "channel").map(n => n.id);
  const colorFor = (id) => channelColors[channelIds.indexOf(id) % channelColors.length];

  const nodes = state.graph.nodes.map(d => ({ ...d }));
  const links = state.graph.links.map(d => ({ ...d }));

  const linkEl = svg.append("g")
    .attr("stroke", "#bbb")
    .attr("stroke-opacity", 0.5)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", d => Math.sqrt(d.weight));

  const nodeEl = svg.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g");

  nodeEl.append("circle")
    .attr("r", d => d.type === "channel" ? 8 + Math.sqrt(d.size) * 2 : 4 + Math.sqrt(d.size))
    .attr("fill", d => d.type === "channel" ? colorFor(d.id) : "#bcae92")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5)
    .style("cursor", d => d.type === "topic" ? "pointer" : "default")
    .on("click", (event, d) => {
      if (d.type === "topic") {
        const topicLabel = d.label;
        state.filter.topic = topicLabel;
        writeFiltersToUrl();
        renderClaims();
        renderVideos();
        document.getElementById("videos-table").scrollIntoView({ behavior: "smooth" });
      }
    });

  nodeEl.append("text")
    .attr("dy", d => d.type === "channel" ? -14 : -8)
    .attr("text-anchor", "middle")
    .style("font-size", d => d.type === "channel" ? "12px" : "10px")
    .style("font-weight", d => d.type === "channel" ? "600" : "400")
    .style("fill", "#333")
    .style("pointer-events", "none")
    .text(d => d.label);

  nodeEl.append("title").text(d => `${d.type}: ${d.label} (${d.size})`);

  nodeEl.on("mouseover", (event, d) => {
    const connected = new Set([d.id]);
    links.forEach(l => {
      if (l.source.id === d.id || l.source === d.id) connected.add(l.target.id || l.target);
      if (l.target.id === d.id || l.target === d.id) connected.add(l.source.id || l.source);
    });
    nodeEl.style("opacity", n => connected.has(n.id) ? 1 : 0.2);
    linkEl.style("opacity", l => (l.source.id === d.id || l.target.id === d.id) ? 0.9 : 0.05);
  }).on("mouseout", () => {
    nodeEl.style("opacity", 1);
    linkEl.style("opacity", 0.5);
  });

  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(80))
    .force("charge", d3.forceManyBody().strength(-240))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => d.type === "channel" ? 24 : 12));

  sim.on("tick", () => {
    linkEl
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    nodeEl.attr("transform", d => `translate(${d.x}, ${d.y})`);
  });

  const drag = d3.drag()
    .on("start", (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
    .on("end", (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
  nodeEl.call(drag);
}
function renderSignatures() {
  const container = document.getElementById("signatures");
  container.innerHTML = '<div class="signatures-grid"></div>';
  const grid = container.querySelector(".signatures-grid");

  const entries = Object.entries(state.signatures).sort((a, b) => a[1].channel_name.localeCompare(b[1].channel_name));
  if (!entries.length) {
    container.innerHTML = "<p style='color:var(--muted)'>No signatures yet.</p>";
    return;
  }

  for (const [cid, sig] of entries) {
    const card = document.createElement("div");
    card.className = "signature-card";
    const heading = sig.mode === "distinctive" ? "Distinctive topics" : "Topics covered";
    const top = (sig.topics || []).slice(0, 8);
    const chips = top.map(t =>
      `<span class="topic-chip" data-topic="${t.topic}">${t.topic}</span>`
    ).join(" ");
    card.innerHTML = `
      <h3>${sig.channel_name}</h3>
      <p class="meta">${sig.total_videos} video${sig.total_videos === 1 ? "" : "s"} · ${heading}</p>
      <div>${chips || "<span class='meta'>No topics yet</span>"}</div>
    `;
    card.querySelectorAll(".topic-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        state.filter.topic = chip.dataset.topic;
        writeFiltersToUrl();
        renderClaims();
        renderVideos();
        document.getElementById("videos-table").scrollIntoView({ behavior: "smooth" });
      });
    });
    grid.appendChild(card);
  }
}
function renderClaims() {
  const tbody = document.querySelector("#claims-table tbody");
  tbody.innerHTML = "";
  const filtersDiv = document.getElementById("claims-filters");
  filtersDiv.innerHTML = state.filter.topic
    ? `<p style="color:var(--muted);font-size:13px;">Filtered to topic: <strong>${state.filter.topic}</strong> <a href="#" id="clear-claim-topic">clear</a></p>`
    : "";
  const clearLink = document.getElementById("clear-claim-topic");
  if (clearLink) {
    clearLink.addEventListener("click", (e) => {
      e.preventDefault();
      state.filter.topic = null;
      writeFiltersToUrl();
      renderClaims();
      renderVideos();
    });
  }

  const rows = [];
  for (const v of state.videos) {
    if (v.transcript_source === "unavailable") continue;
    if (state.filter.topic && !v.topics.map(normalizeForMatch).includes(normalizeForMatch(state.filter.topic))) continue;
    if (state.filter.channel && v.channel_id !== state.filter.channel) continue;
    for (const claim of v.key_claims || []) {
      rows.push({ claim, channel: v.channel_name, title: v.title, url: v.url });
    }
  }

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="3" style="color:var(--muted);padding:16px;">No claims match current filters.</td></tr>`;
    return;
  }

  for (const r of rows.slice(0, 200)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.claim)}</td>
      <td>${escapeHtml(r.channel)}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a></td>
    `;
    tbody.appendChild(tr);
  }
}

function normalizeForMatch(s) {
  return s.trim().toLowerCase();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function renderVideos() {
  const tbody = document.querySelector("#videos-table tbody");
  tbody.innerHTML = "";

  let rows = [...state.videos];

  if (state.filter.topic) {
    const t = normalizeForMatch(state.filter.topic);
    rows = rows.filter(v => (v.topics || []).map(normalizeForMatch).includes(t));
  }
  if (state.filter.channel) {
    rows = rows.filter(v => v.channel_id === state.filter.channel);
  }
  if (state.filter.text) {
    const q = state.filter.text.toLowerCase();
    rows = rows.filter(v =>
      (v.title || "").toLowerCase().includes(q) ||
      (v.channel_name || "").toLowerCase().includes(q) ||
      (v.summary || "").toLowerCase().includes(q) ||
      (v.topics || []).some(t => t.toLowerCase().includes(q))
    );
  }

  if (state.sortBy === "date") {
    rows.sort((a, b) => b.published_at.localeCompare(a.published_at));
  } else if (state.sortBy === "channel") {
    rows.sort((a, b) =>
      (a.channel_name || "").localeCompare(b.channel_name || "") ||
      b.published_at.localeCompare(a.published_at)
    );
  }

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--muted);padding:16px;">No videos match current filters.</td></tr>`;
    return;
  }

  for (const v of rows) {
    const tr = document.createElement("tr");
    const dateStr = (v.published_at || "").slice(0, 10);
    const speakersCell = (v.speakers && v.speakers.length)
      ? escapeHtml(v.speakers.join(", "))
      : "<span style='color:var(--muted)'>—</span>";
    const topicChips = (v.topics || []).map(t =>
      `<span class="topic-chip" data-topic="${escapeHtml(t)}">${escapeHtml(t)}</span>`
    ).join(" ");
    const summaryCell = v.transcript_source === "unavailable"
      ? `<span class="unavailable-badge">transcript unavailable</span>`
      : `<div class="summary-cell collapsed" data-full="${escapeHtml(v.summary || '')}">${escapeHtml(v.summary || '')}</div>`;
    tr.innerHTML = `
      <td>${dateStr}</td>
      <td>${escapeHtml(v.channel_name || "")}</td>
      <td><a href="${v.url}" target="_blank" rel="noopener">${escapeHtml(v.title || "")}</a></td>
      <td>${speakersCell}</td>
      <td>${topicChips}</td>
      <td>${summaryCell}</td>
    `;
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll(".topic-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      state.filter.topic = chip.dataset.topic;
      writeFiltersToUrl();
      renderClaims();
      renderVideos();
    });
  });
  tbody.querySelectorAll(".summary-cell").forEach(cell => {
    cell.addEventListener("click", () => cell.classList.toggle("collapsed"));
  });
}

function wireFilters() {
  const search = document.getElementById("video-search");
  search.value = state.filter.text || "";
  search.addEventListener("input", (e) => {
    state.filter.text = e.target.value;
    writeFiltersToUrl();
    renderVideos();
  });

  const sortSel = document.getElementById("sort-by");
  sortSel.value = state.sortBy;
  sortSel.addEventListener("change", (e) => {
    state.sortBy = e.target.value;
    renderVideos();
  });
}

boot();
