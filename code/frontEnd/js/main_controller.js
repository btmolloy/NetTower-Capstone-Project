const canvas = document.getElementById("topology-canvas");
const canvasEmpty = document.getElementById("canvas-empty");
const stopButton = document.getElementById("stop-session-btn");
const modeButton = document.getElementById("map-mode-btn");
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
const MODE_ORDER = ["2d", "3d", "idle"];
const MODE_LABELS = {
  "2d": "2D",
  "3d": "3D",
  idle: "Idle",
};

const state = {
  mode: "2d",
  nodes: new Map(),
  edges: [],
  hitRegions: [],
  selectedHostId: null,
  selectedHost: null,
  refreshIntervalMs: 3000,
  hostLimit: 250,
  edgeLimit: 500,
  pollingTimer: null,
  fetchInFlight: false,
  animationHandle: null,
  width: 1,
  height: 1,
  idleAngle: 0,
  camera: {
    yaw: -0.58,
    pitch: 0.96,
    distance: 900,
    focalLength: 780,
    panX: 0,
    panZ: 0,
    dragging: false,
    dragMode: null,
    dragDistance: 0,
    pointerId: null,
    lastX: 0,
    lastY: 0,
    lastDragAt: 0,
  },
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
    return "#35d38c";
  }
  if (age <= 120) {
    return "#d9953f";
  }
  return "#bb3f5f";
}

function edgeColor(lastSeen) {
  const age = ageSeconds(lastSeen);
  if (age <= 30) {
    return "rgba(52, 208, 139, 0.48)";
  }
  if (age <= 120) {
    return "rgba(220, 153, 74, 0.34)";
  }
  return "rgba(182, 70, 98, 0.26)";
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

function modeCaption() {
  if (state.mode === "2d") {
    return "2D mode shows active topology layout optimized for analysis.";
  }
  if (state.mode === "3d") {
    return "3D mode: drag to orbit, Shift-drag or right-drag to pan, scroll to zoom.";
  }
  return "Idle mode: cinematic rotation for passive wallboard monitoring.";
}

function updateModeLabel() {
  modeButton.textContent = `Mode: ${MODE_LABELS[state.mode]}`;
  liveCaptionElement.textContent = modeCaption();
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
      z: randomRange(-1.2, 1.2),
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
    renderHostDetails(state.nodes.get(state.selectedHostId).host);
  } else if (state.selectedHostId) {
    closeHostDrawer();
  }

  const lastUpdate = snapshot.captured_at ? new Date(snapshot.captured_at).toLocaleTimeString() : "--";
  countsStatusElement.textContent = `Hosts: ${validHosts.length} | Edges: ${validEdges.length}`;
  updatedStatusElement.textContent = `Last update: ${lastUpdate}`;
  canvasEmpty.classList.toggle("is-hidden", validHosts.length > 0);
}

function drawBackground() {
  const gradient = ctx.createLinearGradient(0, 0, state.width, state.height);
  gradient.addColorStop(0, "#090c12");
  gradient.addColorStop(0.55, "#131924");
  gradient.addColorStop(1, "#1b1318");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, state.width, state.height);
}

function projectIdleNode(node) {
  const cx = state.width / 2;
  const cy = state.height / 2;
  const worldX = node.x - cx;
  const worldY = node.y - cy;
  const worldZ = node.z * 180;

  const c = Math.cos(state.idleAngle);
  const s = Math.sin(state.idleAngle);

  const rx = worldX * c + worldZ * s;
  const rz = worldZ * c - worldX * s;
  const perspective = clamp(1 + rz / 700, 0.5, 1.8);

  return {
    x: cx + rx * perspective,
    y: cy + worldY * perspective,
    scale: perspective,
    depth: rz,
  };
}

function nodeWorldPosition(node) {
  const cx = state.width / 2;
  const cy = state.height / 2;
  const x = (node.x - cx) * 1.18;
  const z = (node.y - cy) * 1.18;
  const recentBoost = Math.max(0, 110 - ageSeconds(node.host.last_seen)) * 0.08;
  const y = 16 + Math.min(80, node.degree * 4.8) + recentBoost;
  return { x, y, z };
}

function worldToCameraPoint(point) {
  const {
    yaw,
    pitch,
    panX,
    panZ,
  } = state.camera;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);

  const shiftedX = point.x - panX;
  const shiftedZ = point.z - panZ;

  let x = shiftedX * cy - shiftedZ * sy;
  let z = shiftedX * sy + shiftedZ * cy;
  let y = point.y;

  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);

  // Rotate world for an above-looking camera pitch so 3D starts in a top-down perspective.
  const y2 = y * cp + z * sp;
  const z2 = -y * sp + z * cp;

  return {
    x,
    y: y2,
    z: z2,
  };
}

function cameraToScreenPoint(cameraPoint) {
  const {
    distance,
    focalLength,
  } = state.camera;

  const depth = cameraPoint.z + distance;
  if (depth <= 1) {
    return null;
  }

  const scale = focalLength / depth;
  return {
    x: state.width / 2 + cameraPoint.x * scale,
    y: state.height * 0.72 - cameraPoint.y * scale,
    scale,
    depth,
  };
}

function project3DPoint(point, nearDepth = 50) {
  const cameraPoint = worldToCameraPoint(point);
  const projected = cameraToScreenPoint(cameraPoint);
  if (!projected || projected.depth <= nearDepth) {
    return null;
  }
  return projected;
}

function panCameraByPixels(dx, dy) {
  const scale = (state.camera.distance / state.camera.focalLength) * 1.55;
  const cy = Math.cos(state.camera.yaw);
  const sy = Math.sin(state.camera.yaw);

  // Horizontal drag moves along camera-right; vertical drag moves along camera-forward on ground plane.
  const rightX = cy;
  const rightZ = sy;
  const forwardX = -sy;
  const forwardZ = cy;

  state.camera.panX -= dx * scale * rightX;
  state.camera.panZ -= dx * scale * rightZ;
  state.camera.panX += dy * scale * forwardX;
  state.camera.panZ += dy * scale * forwardZ;

  state.camera.panX = clamp(state.camera.panX, -3800, 3800);
  state.camera.panZ = clamp(state.camera.panZ, -3800, 3800);
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  const parsed = Number.parseInt(normalized, 16);
  return {
    r: (parsed >> 16) & 255,
    g: (parsed >> 8) & 255,
    b: parsed & 255,
  };
}

function shadeHex(hex, amount) {
  const rgb = hexToRgb(hex);
  const r = clamp(rgb.r + amount, 0, 255);
  const g = clamp(rgb.g + amount, 0, 255);
  const b = clamp(rgb.b + amount, 0, 255);
  return `rgb(${r}, ${g}, ${b})`;
}

function drawWireframeGrid() {
  const step = 120;
  const halfSpan = Math.ceil(
    Math.max(2600, Math.max(state.width, state.height) * 3.6) / step,
  ) * step;
  const centerX = Math.round(state.camera.panX / step) * step;
  const centerZ = Math.round(state.camera.panZ / step) * step;
  const minX = centerX - halfSpan;
  const maxX = centerX + halfSpan;
  const minZ = centerZ - halfSpan;
  const maxZ = centerZ + halfSpan;
  const majorEvery = step * 4;
  const y = 0;
  const nearDepth = 28;

  const drawGridSegment = (
    startWorld,
    endWorld,
    isMajor,
    majorColor,
    minorColor,
  ) => {
    let cameraA = worldToCameraPoint(startWorld);
    let cameraB = worldToCameraPoint(endWorld);

    let depthA = cameraA.z + state.camera.distance;
    let depthB = cameraB.z + state.camera.distance;

    if (depthA <= nearDepth && depthB <= nearDepth) {
      return;
    }

    // Clip segments to near plane so close grid lines never disappear.
    if (depthA <= nearDepth || depthB <= nearDepth) {
      const t = (nearDepth - depthA) / (depthB - depthA);
      const clipped = {
        x: cameraA.x + (cameraB.x - cameraA.x) * t,
        y: cameraA.y + (cameraB.y - cameraA.y) * t,
        z: cameraA.z + (cameraB.z - cameraA.z) * t,
      };
      if (depthA <= nearDepth) {
        cameraA = clipped;
        depthA = nearDepth;
      } else {
        cameraB = clipped;
        depthB = nearDepth;
      }
    }

    const start = cameraToScreenPoint(cameraA);
    const end = cameraToScreenPoint(cameraB);
    if (!start || !end) {
      return;
    }

    const closestDepth = Math.min(start.depth, end.depth);
    const depthBoost = 1 - closestDepth / (state.camera.distance + halfSpan);
    const alpha = isMajor
      ? clamp(0.46 + depthBoost * 0.26, 0.34, 0.78)
      : clamp(0.24 + depthBoost * 0.2, 0.18, 0.56);
    ctx.strokeStyle = `${isMajor ? majorColor : minorColor}${alpha})`;
    ctx.lineWidth = isMajor ? 1.55 : 1.06;
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  };

  ctx.save();
  ctx.lineCap = "round";

  for (let x = minX; x <= maxX; x += step) {
    const isMajor = Math.abs(x / majorEvery - Math.round(x / majorEvery)) < 1e-6;
    drawGridSegment(
      { x, y, z: minZ },
      { x, y, z: maxZ },
      isMajor,
      "rgba(222, 104, 136, ",
      "rgba(178, 62, 92, ",
    );
  }

  for (let z = minZ; z <= maxZ; z += step) {
    const isMajor = Math.abs(z / majorEvery - Math.round(z / majorEvery)) < 1e-6;
    drawGridSegment(
      { x: minX, y, z },
      { x: maxX, y, z },
      isMajor,
      "rgba(198, 88, 118, ",
      "rgba(144, 52, 76, ",
    );
  }
  ctx.restore();
}

function drawCube(world, size, height, baseColor, selected) {
  const half = size / 2;
  const vertices = [
    { x: -half, y: 0, z: -half },
    { x: half, y: 0, z: -half },
    { x: half, y: 0, z: half },
    { x: -half, y: 0, z: half },
    { x: -half, y: height, z: -half },
    { x: half, y: height, z: -half },
    { x: half, y: height, z: half },
    { x: -half, y: height, z: half },
  ];

  const projected = vertices.map((vertex) => project3DPoint({
    x: world.x + vertex.x,
    y: world.y + vertex.y,
    z: world.z + vertex.z,
  }));
  if (projected.some((point) => point === null)) {
    return null;
  }

  const p = projected;
  const drawFace = (indices, fillStyle, strokeStyle = null) => {
    ctx.fillStyle = fillStyle;
    ctx.beginPath();
    ctx.moveTo(p[indices[0]].x, p[indices[0]].y);
    for (let i = 1; i < indices.length; i += 1) {
      ctx.lineTo(p[indices[i]].x, p[indices[i]].y);
    }
    ctx.closePath();
    ctx.fill();
    if (strokeStyle) {
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
  };

  const faces = [
    { indices: [4, 5, 6, 7], color: shadeHex(baseColor, 30) },  // top
    { indices: [0, 1, 5, 4], color: shadeHex(baseColor, -7) },  // front
    { indices: [1, 2, 6, 5], color: shadeHex(baseColor, -14) }, // right
    { indices: [2, 3, 7, 6], color: shadeHex(baseColor, -22) }, // back
    { indices: [3, 0, 4, 7], color: shadeHex(baseColor, -12) }, // left
  ].map((face) => ({
    ...face,
    avgDepth: face.indices.reduce((sum, idx) => sum + p[idx].depth, 0) / face.indices.length,
  }));

  // Draw far faces first so near faces properly overlap.
  faces.sort((a, b) => b.avgDepth - a.avgDepth);
  for (const face of faces) {
    drawFace(face.indices, face.color, "rgba(22, 12, 17, 0.55)");
  }

  ctx.strokeStyle = "rgba(12, 6, 10, 0.72)";
  ctx.lineWidth = 1.02;
  const edges = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [4, 0], [5, 1], [6, 2], [7, 3],
  ];
  for (const [a, b] of edges) {
    ctx.beginPath();
    ctx.moveTo(p[a].x, p[a].y);
    ctx.lineTo(p[b].x, p[b].y);
    ctx.stroke();
  }

  const topCenter = project3DPoint({
    x: world.x,
    y: world.y + height,
    z: world.z,
  });
  if (!topCenter) {
    return null;
  }

  // Subtle crown lines to read more like a compact tower than a flat box.
  const crownInset = clamp(size * topCenter.scale * 0.24, 2.2, 5.5);
  ctx.strokeStyle = "rgba(243, 222, 230, 0.6)";
  ctx.lineWidth = 0.9;
  ctx.beginPath();
  ctx.moveTo(p[4].x + crownInset, p[4].y + crownInset);
  ctx.lineTo(p[5].x - crownInset, p[5].y + crownInset);
  ctx.lineTo(p[6].x - crownInset, p[6].y - crownInset);
  ctx.lineTo(p[7].x + crownInset, p[7].y - crownInset);
  ctx.closePath();
  ctx.stroke();

  if (selected) {
    ctx.strokeStyle = "rgba(244, 232, 236, 0.95)";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.arc(topCenter.x, topCenter.y, Math.max(10, size * topCenter.scale * 0.95), 0, Math.PI * 2);
    ctx.stroke();
  }

  return {
    x: topCenter.x,
    y: topCenter.y,
    radius: Math.max(10, size * topCenter.scale * 1.1),
    depth: topCenter.depth,
  };
}

function drawNodesAndEdges2D(projectionForNode) {
  const projections = new Map();
  state.hitRegions = [];
  for (const [hostId, node] of state.nodes.entries()) {
    projections.set(hostId, projectionForNode(node));
  }

  ctx.save();
  ctx.lineCap = "round";
  for (const edge of state.edges) {
    const a = projections.get(edge.a_host_id);
    const b = projections.get(edge.b_host_id);
    if (!a || !b) {
      continue;
    }
    ctx.strokeStyle = edgeColor(edge.last_seen);
    ctx.lineWidth = clamp(((a.scale + b.scale) / 2) * 1.8, 0.8, 3.4);
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
    const selected = state.selectedHostId === node.host.host_id;

    ctx.beginPath();
    ctx.fillStyle = "rgba(5, 7, 11, 0.45)";
    ctx.arc(x + 2, y + 2, radius + 0.7, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.fillStyle = hostRecencyColor(node.host.last_seen);
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    if (selected) {
      ctx.beginPath();
      ctx.strokeStyle = "rgba(242, 232, 236, 0.95)";
      ctx.lineWidth = 2.1;
      ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(236, 242, 250, 0.92)";
    ctx.font = `${Math.max(10, Math.round(11 * projected.scale))}px "Avenir Next", sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(nodeLabel(node.host), x, y - radius - 6);

    state.hitRegions.push({
      hostId: node.host.host_id,
      x,
      y,
      radius: radius + 9,
    });
  }
  ctx.restore();
}

function drawMode2D() {
  drawNodesAndEdges2D((node) => ({
    x: node.x,
    y: node.y,
    scale: 1,
    depth: 0,
  }));
}

function drawModeIdle() {
  drawNodesAndEdges2D((node) => projectIdleNode(node));
}

function drawMode3D() {
  state.hitRegions = [];
  drawWireframeGrid();

  const nodeData = [];
  for (const node of state.nodes.values()) {
    const world = nodeWorldPosition(node);
    nodeData.push({
      node,
      world,
      size: clamp(16 + node.degree * 1.8, 16, 38),
      height: clamp(16 + node.degree * 3.8, 18, 74),
      depth: world.z,
    });
  }
  const nodeDataById = new Map(
    nodeData.map((entry) => [entry.node.host.host_id, entry]),
  );

  ctx.save();
  ctx.lineCap = "round";
  for (const edge of state.edges) {
    const aNode = nodeDataById.get(edge.a_host_id);
    const bNode = nodeDataById.get(edge.b_host_id);
    if (!aNode || !bNode) {
      continue;
    }

    const aProjected = project3DPoint({
      x: aNode.world.x,
      y: aNode.world.y + aNode.height,
      z: aNode.world.z,
    });
    const bProjected = project3DPoint({
      x: bNode.world.x,
      y: bNode.world.y + bNode.height,
      z: bNode.world.z,
    });
    if (!aProjected || !bProjected) {
      continue;
    }

    ctx.strokeStyle = edgeColor(edge.last_seen);
    ctx.lineWidth = clamp(((aProjected.scale + bProjected.scale) / 2) * 3.2, 1.0, 4.0);
    ctx.beginPath();
    ctx.moveTo(aProjected.x, aProjected.y);
    ctx.lineTo(bProjected.x, bProjected.y);
    ctx.stroke();
  }
  ctx.restore();

  const sorted = nodeData.sort((left, right) => left.world.z - right.world.z);
  for (const entry of sorted) {
    const base = hostRecencyColor(entry.node.host.last_seen);
    const selected = state.selectedHostId === entry.node.host.host_id;
    const hit = drawCube(entry.world, entry.size, entry.height, base, selected);
    if (!hit) {
      continue;
    }

    ctx.fillStyle = "rgba(236, 242, 250, 0.94)";
    ctx.font = `${Math.max(10, Math.round(11 * hit.radius * 0.08))}px "Avenir Next", sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(nodeLabel(entry.node.host), hit.x, hit.y - hit.radius - 4);

    state.hitRegions.push({
      hostId: entry.node.host.host_id,
      x: hit.x,
      y: hit.y,
      radius: hit.radius,
      depth: hit.depth,
    });
  }
}

function drawTopology() {
  drawBackground();

  if (state.mode === "2d") {
    drawMode2D();
    return;
  }
  if (state.mode === "3d") {
    drawMode3D();
    return;
  }
  drawModeIdle();
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
  const repulsion = state.mode === "idle" ? 2600 : 1900;
  const springStrength = 0.0048;
  const damping = 0.88;
  const attraction = 0.0017;
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

    if (state.mode === "idle") {
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
  if (state.mode === "idle") {
    state.idleAngle += 0.0034;
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
    } else {
      setStatus("Session is running.", "info");
    }
  } catch (error) {
    setStatus(`Topology poll failed: ${error.message}`, "error");
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

function pickHitNode(x, y) {
  let nearest = null;
  let nearestDistance = Number.POSITIVE_INFINITY;

  const orderedRegions = state.hitRegions
    .slice()
    .sort((left, right) => (right.depth || 0) - (left.depth || 0));

  for (const region of orderedRegions) {
    const dx = x - region.x;
    const dy = y - region.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist <= region.radius && dist < nearestDistance) {
      nearest = region;
      nearestDistance = dist;
    }
  }

  return nearest;
}

canvas.addEventListener("contextmenu", (event) => {
  event.preventDefault();
});

canvas.addEventListener("pointerdown", (event) => {
  if (state.mode !== "3d") {
    return;
  }

  event.preventDefault();
  state.camera.dragging = true;
  state.camera.dragMode = (event.button === 2 || event.shiftKey || event.altKey) ? "pan" : "orbit";
  state.camera.dragDistance = 0;
  state.camera.pointerId = event.pointerId;
  state.camera.lastX = event.clientX;
  state.camera.lastY = event.clientY;
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", (event) => {
  if (!state.camera.dragging || state.mode !== "3d") {
    return;
  }

  const dx = event.clientX - state.camera.lastX;
  const dy = event.clientY - state.camera.lastY;
  state.camera.lastX = event.clientX;
  state.camera.lastY = event.clientY;
  state.camera.dragDistance += Math.abs(dx) + Math.abs(dy);

  if (state.camera.dragMode === "pan") {
    panCameraByPixels(dx, dy);
  } else {
    state.camera.yaw += dx * 0.0055;
    state.camera.pitch = clamp(state.camera.pitch - dy * 0.0036, 0.52, 1.34);
  }
});

canvas.addEventListener("pointerup", (event) => {
  if (state.camera.pointerId === event.pointerId) {
    canvas.releasePointerCapture(event.pointerId);
  }
  if (state.camera.dragDistance > 4) {
    state.camera.lastDragAt = Date.now();
  }
  state.camera.dragging = false;
  state.camera.dragMode = null;
  state.camera.pointerId = null;
  state.camera.dragDistance = 0;
});

canvas.addEventListener("pointercancel", () => {
  state.camera.dragging = false;
  state.camera.dragMode = null;
  state.camera.pointerId = null;
  state.camera.dragDistance = 0;
});

canvas.addEventListener("wheel", (event) => {
  if (state.mode !== "3d") {
    return;
  }

  event.preventDefault();
  state.camera.distance = clamp(state.camera.distance + event.deltaY * 0.45, 420, 2100);
}, { passive: false });

window.addEventListener("keydown", (event) => {
  if (state.mode !== "3d") {
    return;
  }

  const targetTag = event.target && event.target.tagName ? event.target.tagName.toLowerCase() : "";
  if (targetTag === "input" || targetTag === "textarea") {
    return;
  }

  const panStep = Math.max(26, state.camera.distance * 0.03);
  const zoomStep = 55;

  if (event.key === "+" || event.key === "=") {
    state.camera.distance = clamp(state.camera.distance - zoomStep, 420, 2100);
    event.preventDefault();
    return;
  }
  if (event.key === "-" || event.key === "_") {
    state.camera.distance = clamp(state.camera.distance + zoomStep, 420, 2100);
    event.preventDefault();
    return;
  }

  if (event.key === "ArrowLeft") {
    panCameraByPixels(panStep, 0);
    event.preventDefault();
    return;
  }
  if (event.key === "ArrowRight") {
    panCameraByPixels(-panStep, 0);
    event.preventDefault();
    return;
  }
  if (event.key === "ArrowUp") {
    panCameraByPixels(0, panStep);
    event.preventDefault();
    return;
  }
  if (event.key === "ArrowDown") {
    panCameraByPixels(0, -panStep);
    event.preventDefault();
  }
});

canvas.addEventListener("click", (event) => {
  if (state.mode === "3d" && Date.now() - state.camera.lastDragAt < 180) {
    return;
  }

  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const hit = pickHitNode(x, y);

  if (!hit) {
    closeHostDrawer();
    return;
  }

  const selected = state.nodes.get(hit.hostId);
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

modeButton.addEventListener("click", () => {
  const index = MODE_ORDER.indexOf(state.mode);
  const nextIndex = (index + 1) % MODE_ORDER.length;
  state.mode = MODE_ORDER[nextIndex];
  updateModeLabel();
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
  updateModeLabel();
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
