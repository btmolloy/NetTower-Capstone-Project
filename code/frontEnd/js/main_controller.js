const canvas = document.getElementById("topology-canvas");
const canvasEmpty = document.getElementById("canvas-empty");
const stopButton = document.getElementById("stop-session-btn");
const mapModeButton = document.getElementById("map-mode-btn");
const settingsButton = document.getElementById("settings-btn");
const mainStatusElement = document.getElementById("main-status");
const countsStatusElement = document.getElementById("counts-status");
const updatedStatusElement = document.getElementById("updated-status");
const liveCaptionElement = document.getElementById("live-caption");

const hostDrawer = document.getElementById("host-drawer");
const hostDetailsElement = document.getElementById("host-details");
const closeDrawerButton = document.getElementById("close-drawer-btn");

const settingsDrawer = document.getElementById("settings-drawer");
const closeSettingsButton = document.getElementById("close-settings-btn");
const settingsForm = document.getElementById("settings-form");
const refreshIntervalInput = document.getElementById("refresh-interval-input");
const hostLimitInput = document.getElementById("host-limit-input");
const edgeLimitInput = document.getElementById("edge-limit-input");
const drawerBackdrop = document.getElementById("drawer-backdrop");

const ctx = canvas.getContext("2d");

const state = {
  mode: "2d",
  nodes: new Map(),
  edges: [],
  visibleNodeIds: new Set(),
  hitRegions: [],
  selectedHostId: null,
  selectedHost: null,
  refreshIntervalMs: 3000,
  hostLimit: 250,
  edgeLimit: 500,
  pollingTimer: null,
  fetchInFlight: false,
  cameraAngle: 0,
  animationHandle: null,
  width: 1,
  height: 1,
};

const resizeObserver = new ResizeObserver(() => {
  resizeCanvas();
});
resizeObserver.observe(canvas.parentElement);

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseTimestamp(value) {
  if (!value) {
    return 0;
  }
  const ts = Date.parse(String(value));
  return Number.isFinite(ts) ? ts : 0;
}

function ageSeconds(value) {
  const ts = parseTimestamp(value);
  if (!ts) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.max(0, (Date.now() - ts) / 1000);
}

function hostRecencyColor(lastSeen) {
  const age = ageSeconds(lastSeen);
  if (age <= 30) {
    return "#1ad47a";
  }
  if (age <= 120) {
    return "#ffb24d";
  }
  return "#f36365";
}

function edgeColor(lastSeen) {
  const age = ageSeconds(lastSeen);
  if (age <= 30) {
    return "rgba(30, 215, 138, 0.48)";
  }
  if (age <= 120) {
    return "rgba(255, 172, 77, 0.35)";
  }
  return "rgba(228, 117, 122, 0.24)";
}

function setStatus(message, level = "info") {
  mainStatusElement.textContent = message;
  mainStatusElement.classList.remove("status-info", "status-success", "status-error");
  mainStatusElement.classList.add(`status-${level}`);
}

function setStopping(isStopping) {
  stopButton.disabled = isStopping;
  stopButton.textContent = isStopping ? "Stopping Session..." : "Stop Session";
}

function updateMapModeLabel() {
  mapModeButton.textContent = `Map: ${state.mode === "2d" ? "2D" : "3D"}`;
}

function updateBackdrop() {
  const shouldShow = hostDrawer.classList.contains("is-open")
    || settingsDrawer.classList.contains("is-open");
  drawerBackdrop.classList.toggle("is-visible", shouldShow);
}

function closeHostDrawer() {
  hostDrawer.classList.remove("is-open");
  state.selectedHostId = null;
  state.selectedHost = null;
  updateBackdrop();
}

function openHostDrawer(host) {
  state.selectedHostId = host.host_id;
  state.selectedHost = host;
  renderHostDetails(host);
  hostDrawer.classList.add("is-open");
  updateBackdrop();
}

function closeSettingsDrawer() {
  settingsDrawer.classList.remove("is-open");
  updateBackdrop();
}

function openSettingsDrawer() {
  settingsDrawer.classList.add("is-open");
  updateBackdrop();
}

function formatArray(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return "None";
  }
  return values.map((item) => escapeHtml(item)).join(", ");
}

function formatPorts(ports) {
  if (!Array.isArray(ports) || ports.length === 0) {
    return "None";
  }

  const formatted = ports
    .slice(0, 12)
    .map((entry) => {
      if (!Array.isArray(entry)) {
        return escapeHtml(entry);
      }
      if (entry.length === 3) {
        return `${escapeHtml(entry[0])}/${escapeHtml(entry[1])} ${escapeHtml(entry[2])}`;
      }
      return entry.map((part) => escapeHtml(part)).join(":");
    });
  return formatted.join(", ");
}

function formatTime(value) {
  const ts = parseTimestamp(value);
  if (!ts) {
    return "Unknown";
  }
  return new Date(ts).toLocaleString();
}

function renderHostDetails(host) {
  hostDetailsElement.innerHTML = `
    <div class="detail-row"><span>Host ID</span><strong>${escapeHtml(host.host_id)}</strong></div>
    <div class="detail-row"><span>IPs</span><strong>${formatArray(host.ips)}</strong></div>
    <div class="detail-row"><span>MACs</span><strong>${formatArray(host.macs)}</strong></div>
    <div class="detail-row"><span>Vendor</span><strong>${escapeHtml(host.vendor || "Unknown")}</strong></div>
    <div class="detail-row"><span>OS Guess</span><strong>${escapeHtml(host.os_guess || "Unknown")}</strong></div>
    <div class="detail-row"><span>First Seen</span><strong>${escapeHtml(formatTime(host.first_seen))}</strong></div>
    <div class="detail-row"><span>Last Seen</span><strong>${escapeHtml(formatTime(host.last_seen))}</strong></div>
    <div class="detail-row"><span>Ports</span><strong>${formatPorts(host.ports)}</strong></div>
  `;
}

function nodeLabel(host) {
  if (Array.isArray(host.ips) && host.ips.length > 0) {
    return host.ips[0];
  }
  if (Array.isArray(host.macs) && host.macs.length > 0) {
    return host.macs[0];
  }
  return host.host_id;
}

function randomRange(min, max) {
  return min + Math.random() * (max - min);
}

function ensureNode(host) {
  let node = state.nodes.get(host.host_id);
  if (!node) {
    node = {
      host,
      x: randomRange(80, Math.max(120, state.width - 80)),
      y: randomRange(80, Math.max(120, state.height - 80)),
      z: randomRange(-1, 1),
      vx: randomRange(-0.25, 0.25),
      vy: randomRange(-0.25, 0.25),
      vz: randomRange(-0.003, 0.003),
      degree: 0,
      radius: 8,
    };
    state.nodes.set(host.host_id, node);
  } else {
    node.host = host;
  }
  return node;
}

function normalizeHost(raw) {
  return {
    host_id: String(raw.host_id || ""),
    ips: Array.isArray(raw.ips) ? raw.ips.filter(Boolean).map(String) : [],
    macs: Array.isArray(raw.macs) ? raw.macs.filter(Boolean).map(String) : [],
    vendor: raw.vendor ? String(raw.vendor) : null,
    os_guess: raw.os_guess ? String(raw.os_guess) : null,
    first_seen: raw.first_seen ? String(raw.first_seen) : null,
    last_seen: raw.last_seen ? String(raw.last_seen) : null,
    ports: Array.isArray(raw.ports) ? raw.ports : [],
  };
}

function normalizeEdge(raw) {
  return {
    edge_key: String(raw.edge_key || ""),
    a_host_id: String(raw.a_host_id || ""),
    b_host_id: String(raw.b_host_id || ""),
    proto: raw.proto ? String(raw.proto) : "",
    first_seen: raw.first_seen ? String(raw.first_seen) : null,
    last_seen: raw.last_seen ? String(raw.last_seen) : null,
    count: Number.isFinite(Number(raw.count)) ? Number(raw.count) : 0,
    ports: Array.isArray(raw.ports) ? raw.ports : [],
  };
}

function applySnapshot(snapshot) {
  const hosts = Array.isArray(snapshot.hosts) ? snapshot.hosts.map(normalizeHost) : [];
  const edges = Array.isArray(snapshot.edges) ? snapshot.edges.map(normalizeEdge) : [];

  const validHosts = hosts.filter((host) => host.host_id);
  const visibleNodeIds = new Set(validHosts.map((host) => host.host_id));
  state.visibleNodeIds = visibleNodeIds;

  for (const host of validHosts) {
    ensureNode(host);
  }

  for (const existingId of [...state.nodes.keys()]) {
    if (!visibleNodeIds.has(existingId)) {
      state.nodes.delete(existingId);
    }
  }

  const degreeMap = new Map();
  const validEdges = edges.filter(
    (edge) => visibleNodeIds.has(edge.a_host_id) && visibleNodeIds.has(edge.b_host_id),
  );
  for (const edge of validEdges) {
    degreeMap.set(edge.a_host_id, (degreeMap.get(edge.a_host_id) || 0) + 1);
    degreeMap.set(edge.b_host_id, (degreeMap.get(edge.b_host_id) || 0) + 1);
  }

  for (const [hostId, node] of state.nodes.entries()) {
    node.degree = degreeMap.get(hostId) || 0;
    node.radius = clamp(6 + Math.sqrt(node.degree + 1) * 1.8, 7, 16);
  }

  state.edges = validEdges;

  if (state.selectedHostId && state.nodes.has(state.selectedHostId)) {
    const host = state.nodes.get(state.selectedHostId).host;
    state.selectedHost = host;
    renderHostDetails(host);
  } else if (state.selectedHostId) {
    closeHostDrawer();
  }

  const lastUpdate = snapshot.captured_at ? new Date(snapshot.captured_at).toLocaleTimeString() : "--";
  countsStatusElement.textContent = `Hosts: ${validHosts.length} | Edges: ${validEdges.length}`;
  updatedStatusElement.textContent = `Last update: ${lastUpdate}`;

  const hasData = validHosts.length > 0;
  canvasEmpty.classList.toggle("is-hidden", hasData);
}

function projectNode(node) {
  if (state.mode === "2d") {
    return {
      x: node.x,
      y: node.y,
      scale: 1,
      depth: 0,
    };
  }

  const cx = state.width / 2;
  const cy = state.height / 2;
  const worldX = node.x - cx;
  const worldY = node.y - cy;
  const worldZ = node.z * 180;

  const c = Math.cos(state.cameraAngle);
  const s = Math.sin(state.cameraAngle);

  const rx = worldX * c + worldZ * s;
  const rz = worldZ * c - worldX * s;
  const perspective = clamp(1 + rz / 720, 0.52, 1.75);

  return {
    x: cx + rx * perspective,
    y: cy + worldY * perspective,
    scale: perspective,
    depth: rz,
  };
}

function drawBackground() {
  const gradient = ctx.createLinearGradient(0, 0, state.width, state.height);
  gradient.addColorStop(0, "#0d2238");
  gradient.addColorStop(1, "#112f4a");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, state.width, state.height);
}

function drawTopology() {
  drawBackground();

  const projections = new Map();
  state.hitRegions = [];

  for (const [hostId, node] of state.nodes.entries()) {
    projections.set(hostId, projectNode(node));
  }

  ctx.save();
  ctx.lineCap = "round";

  for (const edge of state.edges) {
    const a = projections.get(edge.a_host_id);
    const b = projections.get(edge.b_host_id);
    if (!a || !b) {
      continue;
    }
    const edgeAgeColor = edgeColor(edge.last_seen);
    ctx.strokeStyle = edgeAgeColor;
    ctx.lineWidth = clamp(((a.scale + b.scale) / 2) * 1.8, 0.75, 3.2);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  const drawOrder = [...state.nodes.values()].sort((left, right) => {
    const a = projections.get(left.host.host_id);
    const b = projections.get(right.host.host_id);
    return (a?.depth || 0) - (b?.depth || 0);
  });

  for (const node of drawOrder) {
    const projected = projections.get(node.host.host_id);
    if (!projected) {
      continue;
    }

    const radius = node.radius * projected.scale;
    const x = projected.x;
    const y = projected.y;

    const fill = hostRecencyColor(node.host.last_seen);
    const selected = state.selectedHostId === node.host.host_id;

    ctx.beginPath();
    ctx.fillStyle = "rgba(8, 16, 24, 0.35)";
    ctx.arc(x + 2, y + 3, radius + 0.8, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.fillStyle = fill;
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    if (selected) {
      ctx.beginPath();
      ctx.strokeStyle = "rgba(255,255,255,0.95)";
      ctx.lineWidth = 2.2;
      ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    const label = nodeLabel(node.host);
    ctx.fillStyle = "rgba(235, 246, 255, 0.9)";
    ctx.font = `${Math.max(10, Math.round(11 * projected.scale))}px "Avenir Next", sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(label, x, y - radius - 6);

    state.hitRegions.push({
      hostId: node.host.host_id,
      x,
      y,
      radius: radius + 8,
    });
  }
  ctx.restore();
}

function stepPhysics() {
  const nodes = [...state.nodes.values()];
  if (nodes.length === 0) {
    return;
  }

  const width = state.width;
  const height = state.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const repulsion = state.mode === "3d" ? 2800 : 1900;
  const springStrength = 0.0045;
  const damping = 0.88;
  const attraction = 0.0016;
  const idealEdgeLength = clamp(
    Math.sqrt((width * height) / Math.max(nodes.length, 1)) * 0.85,
    70,
    220,
  );

  for (let i = 0; i < nodes.length; i += 1) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j += 1) {
      const b = nodes[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = dx * dx + dy * dy + 1.0;
      const dist = Math.sqrt(distSq);
      const force = repulsion / distSq;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }
  }

  for (const edge of state.edges) {
    const a = state.nodes.get(edge.a_host_id);
    const b = state.nodes.get(edge.b_host_id);
    if (!a || !b) {
      continue;
    }

    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const force = (dist - idealEdgeLength) * springStrength;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    a.vx += fx;
    a.vy += fy;
    b.vx -= fx;
    b.vy -= fy;
  }

  for (const node of nodes) {
    node.vx += (centerX - node.x) * attraction;
    node.vy += (centerY - node.y) * attraction;

    node.vx *= damping;
    node.vy *= damping;

    node.x += node.vx;
    node.y += node.vy;

    const edgeMargin = node.radius + 18;
    if (node.x < edgeMargin || node.x > width - edgeMargin) {
      node.vx *= -0.75;
      node.x = clamp(node.x, edgeMargin, width - edgeMargin);
    }
    if (node.y < edgeMargin || node.y > height - edgeMargin) {
      node.vy *= -0.75;
      node.y = clamp(node.y, edgeMargin, height - edgeMargin);
    }

    if (state.mode === "3d") {
      node.vz += (-node.z) * 0.0035 + randomRange(-0.0006, 0.0006);
      node.vz *= 0.95;
      node.z = clamp(node.z + node.vz, -1.5, 1.5);
    } else {
      node.z *= 0.95;
      node.vz *= 0.9;
    }
  }
}

function animationLoop() {
  stepPhysics();
  if (state.mode === "3d") {
    state.cameraAngle += 0.0035;
  }
  drawTopology();
  state.animationHandle = window.requestAnimationFrame(animationLoop);
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  state.width = Math.max(1, rect.width);
  state.height = Math.max(1, rect.height);

  canvas.width = Math.max(1, Math.floor(state.width * dpr));
  canvas.height = Math.max(1, Math.floor(state.height * dpr));

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawTopology();
}

async function pollTopology() {
  if (state.fetchInFlight) {
    return;
  }

  state.fetchInFlight = true;
  try {
    const snapshot = await window.nettower.getTopology({
      limitHosts: state.hostLimit,
      limitEdges: state.edgeLimit,
    });

    applySnapshot(snapshot);

    if (snapshot.warning) {
      setStatus(`Topology warning: ${snapshot.warning}`, "error");
      liveCaptionElement.textContent = "Waiting for topology data stream.";
    } else {
      setStatus("Session is running.", "info");
      liveCaptionElement.textContent = "Topology map updates every few seconds from Mongo.";
    }
  } catch (error) {
    setStatus(`Topology poll failed: ${error.message}`, "error");
    liveCaptionElement.textContent = "Unable to refresh topology snapshot.";
  } finally {
    state.fetchInFlight = false;
  }
}

function restartPolling() {
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
    state.pollingTimer = null;
  }
  pollTopology();
  state.pollingTimer = setInterval(pollTopology, state.refreshIntervalMs);
}

canvas.addEventListener("click", (event) => {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  let nearest = null;
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (const region of state.hitRegions) {
    const dx = x - region.x;
    const dy = y - region.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist <= region.radius && dist < nearestDistance) {
      nearest = region;
      nearestDistance = dist;
    }
  }

  if (!nearest) {
    closeHostDrawer();
    return;
  }

  const selected = state.nodes.get(nearest.hostId);
  if (!selected) {
    closeHostDrawer();
    return;
  }

  openHostDrawer(selected.host);
});

settingsButton.addEventListener("click", () => {
  openSettingsDrawer();
});

closeSettingsButton.addEventListener("click", () => {
  closeSettingsDrawer();
});

closeDrawerButton.addEventListener("click", () => {
  closeHostDrawer();
});

drawerBackdrop.addEventListener("click", () => {
  closeHostDrawer();
  closeSettingsDrawer();
});

settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const refreshInterval = clamp(
    Number.parseInt(refreshIntervalInput.value, 10) || 3000,
    500,
    30000,
  );
  const hostLimit = clamp(
    Number.parseInt(hostLimitInput.value, 10) || 250,
    10,
    2000,
  );
  const edgeLimit = clamp(
    Number.parseInt(edgeLimitInput.value, 10) || 500,
    10,
    4000,
  );

  refreshIntervalInput.value = String(refreshInterval);
  hostLimitInput.value = String(hostLimit);
  edgeLimitInput.value = String(edgeLimit);

  state.refreshIntervalMs = refreshInterval;
  state.hostLimit = hostLimit;
  state.edgeLimit = edgeLimit;

  closeSettingsDrawer();
  restartPolling();
});

mapModeButton.addEventListener("click", () => {
  state.mode = state.mode === "2d" ? "3d" : "2d";
  updateMapModeLabel();
});

stopButton.addEventListener("click", async () => {
  setStopping(true);
  setStatus("Requesting graceful shutdown...", "info");

  try {
    await window.nettower.stopSession();
  } catch (error) {
    setStopping(false);
    setStatus(`Failed to stop session: ${error.message}`, "error");
  }
});

function initialize() {
  updateMapModeLabel();
  setStatus("Session is running.", "info");
  resizeCanvas();
  restartPolling();
  animationLoop();
}

window.addEventListener("beforeunload", () => {
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
    state.pollingTimer = null;
  }
  if (state.animationHandle) {
    cancelAnimationFrame(state.animationHandle);
    state.animationHandle = null;
  }
  resizeObserver.disconnect();
});

initialize();
