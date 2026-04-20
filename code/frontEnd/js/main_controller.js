const canvas = document.getElementById("topology-canvas");
const canvasEmpty = document.getElementById("canvas-empty");
const stopButton = document.getElementById("stop-session-btn");
const modeButton = document.getElementById("map-mode-btn");
const hostFilterButton = document.getElementById("host-filter-btn");
const topologyLayoutButton = document.getElementById("topology-layout-btn");
const zoomSlider = document.getElementById("zoom-slider");
const zoomSliderFill = document.getElementById("zoom-slider-fill");
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
const settingsTabDisplayButton = document.getElementById("settings-tab-display");
const settingsTabDataButton = document.getElementById("settings-tab-data");
const settingsPanelDisplay = document.getElementById("settings-panel-display");
const settingsPanelData = document.getElementById("settings-panel-data");
const settingsForm = document.getElementById("settings-form");
const hideStaleToggle = document.getElementById("hide-stale-toggle");
const keepStalePrivateToggle = document.getElementById("keep-stale-private-toggle");
const keepStalePrivateField = document.getElementById("keep-stale-private-field");
const staleDependentOptions = document.getElementById("stale-dependent-options");
const staleThresholdField = document.getElementById("stale-threshold-field");
const staleThresholdInput = document.getElementById("stale-threshold-input");
const activeSensorToggle = document.getElementById("active-sensor-toggle");
const activeIcmpField = document.getElementById("active-icmp-field");
const activeIcmpToggle = document.getElementById("active-icmp-toggle");
const activeNmapField = document.getElementById("active-nmap-field");
const activeNmapToggle = document.getElementById("active-nmap-toggle");
const activeScopeAllField = document.getElementById("active-scope-all-field");
const activeScopeAllToggle = document.getElementById("active-scope-all-toggle");
const refreshIntervalInput = document.getElementById("refresh-interval-input");
const hostLimitInput = document.getElementById("host-limit-input");
const edgeLimitInput = document.getElementById("edge-limit-input");
const refreshDataListButton = document.getElementById("refresh-data-list-btn");
const topologyTextList = document.getElementById("topology-text-list");
const drawerBackdrop = document.getElementById("drawer-backdrop");

const ctx = canvas.getContext("2d");
const MODE_ORDER = ["2d", "3d", "idle"];
const MODE_LABELS = {
  "2d": "2D",
  "3d": "3D",
  idle: "Idle",
};
const HOST_FILTER_ORDER = ["all", "public", "private"];
const HOST_FILTER_LABELS = {
  all: "All",
  public: "Public",
  private: "Private",
};
const TOPOLOGY_LAYOUT_ORDER = ["tree", "star"];
const TOPOLOGY_LAYOUT_LABELS = {
  tree: "Tree",
  star: "Star",
};
const DEFAULT_ZOOM_PERCENT = 33;
const CAMERA_ZOOM_MIN_DISTANCE = 420;
const CAMERA_ZOOM_DEFAULT_DISTANCE = 900;
const CAMERA_ZOOM_MAX_DISTANCE = 1800;

const state = {
  mode: "2d",
  nodes: new Map(),
  edges: [],
  hitRegions: [],
  selectedHostId: null,
  selectedHost: null,
  hostFilter: "all",
  topologyLayoutMode: "tree",
  treeGatewayId: null,
  treeExternalNodeIds: new Set(),
  zoomPercent: DEFAULT_ZOOM_PERCENT,
  localIdentity: {
    interface: null,
    ip: null,
    mac: null,
  },
  lastSnapshot: null,
  refreshIntervalMs: 3000,
  hostLimit: 250,
  edgeLimit: 500,
  activeSensorEnabled: false,
  activeIcmpScanEnabled: true,
  activeNmapScanEnabled: true,
  allowAllActiveTargetsEnabled: false,
  hideStaleHostsEnabled: true,
  keepStalePrivateHostsEnabled: true,
  staleHostThresholdSeconds: 180,
  settingsTab: "display",
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
  view2d: {
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    pointerId: null,
    lastX: 0,
    lastY: 0,
    dragDistance: 0,
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

function normalizeMac(value) {
  if (typeof value !== "string") {
    return null;
  }
  const compact = value.trim().toLowerCase().replaceAll("-", ":");
  return /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/.test(compact) ? compact : null;
}

function parseIPv4(value) {
  const text = String(value || "").trim();
  const octets = text.split(".");
  if (octets.length !== 4) {
    return null;
  }

  const parsed = [];
  for (const octet of octets) {
    if (!/^\d+$/.test(octet)) {
      return null;
    }
    const n = Number.parseInt(octet, 10);
    if (!Number.isInteger(n) || n < 0 || n > 255) {
      return null;
    }
    parsed.push(n);
  }
  return parsed;
}

function isPrivateIPv4(value) {
  const octets = parseIPv4(value);
  if (!octets) {
    return false;
  }
  const [a, b] = octets;
  if (a === 10) {
    return true;
  }
  if (a === 172 && b >= 16 && b <= 31) {
    return true;
  }
  if (a === 192 && b === 168) {
    return true;
  }
  return false;
}

function isPublicIPv4(value) {
  const octets = parseIPv4(value);
  if (!octets) {
    return false;
  }
  if (isPrivateIPv4(value)) {
    return false;
  }

  const [a, b] = octets;
  if (a === 0 || a === 127) {
    return false;
  }
  if (a === 169 && b === 254) {
    return false;
  }
  if (a >= 224) {
    return false;
  }
  if (a === 100 && b >= 64 && b <= 127) {
    return false;
  }

  return true;
}

function isLocalHost(host) {
  const localIp = state.localIdentity.ip ? String(state.localIdentity.ip) : null;
  if (localIp && Array.isArray(host.ips) && host.ips.includes(localIp)) {
    return true;
  }

  const localMac = normalizeMac(state.localIdentity.mac);
  if (localMac && Array.isArray(host.macs)) {
    return host.macs.some((mac) => normalizeMac(mac) === localMac);
  }

  return false;
}

function hostMatchesFilter(host) {
  if (isLocalHost(host)) {
    return true;
  }

  if (state.hostFilter === "all") {
    return true;
  }

  const ips = Array.isArray(host.ips) ? host.ips : [];
  if (state.hostFilter === "private") {
    return ips.some((ip) => isPrivateIPv4(ip));
  }
  if (state.hostFilter === "public") {
    return ips.some((ip) => isPublicIPv4(ip));
  }

  return true;
}

function hostPassesStaleVisibility(host) {
  if (isLocalHost(host)) {
    return true;
  }
  if (!state.hideStaleHostsEnabled) {
    return true;
  }
  if (state.keepStalePrivateHostsEnabled) {
    const ips = Array.isArray(host.ips) ? host.ips : [];
    if (ips.some((ip) => isPrivateIPv4(ip))) {
      return true;
    }
  }
  return ageSeconds(host.last_seen) <= state.staleHostThresholdSeconds;
}

function hostShouldRender(host) {
  return hostMatchesFilter(host) && hostPassesStaleVisibility(host);
}

function primaryHostIp(host) {
  const ips = Array.isArray(host?.ips) ? host.ips : [];
  for (const ip of ips) {
    if (isPrivateIPv4(ip) || isPublicIPv4(ip)) {
      return String(ip);
    }
  }
  return ips.length > 0 ? String(ips[0]) : null;
}

function stableUnitFromString(value) {
  const text = String(value || "");
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function canonicalNodeRole(host) {
  const explicit = String(host?.node_role || "").trim().toLowerCase();
  if (["router", "gateway"].includes(explicit)) {
    return "router";
  }
  if (["switch", "network"].includes(explicit)) {
    return "switch";
  }
  if (explicit === "server") {
    return "server";
  }
  if (["workstation", "client"].includes(explicit)) {
    return "workstation";
  }
  if (explicit === "unknown") {
    return "unknown";
  }

  const role = String(host?.role || "").trim().toLowerCase();
  if (["router", "gateway", "network", "dns", "dhcp", "switch", "firewall"].includes(role)) {
    return "router";
  }
  if (["server", "storage", "nas"].includes(role)) {
    return "server";
  }
  if (["workstation", "client", "printer", "iot"].includes(role)) {
    return "workstation";
  }
  return "unknown";
}

function nodeSortScore(node) {
  const host = node.host || {};
  const role = canonicalNodeRole(host);
  const roleOrder = {
    router: 0,
    switch: 1,
    server: 2,
    workstation: 3,
    unknown: 4,
  };
  const ip = primaryHostIp(host) || "";
  const roleBias = roleOrder[role] ?? 5;
  return `${String(roleBias).padStart(2, "0")}|${ip}|${host.host_id}`;
}

function edgeRelationship(edge) {
  const rel = String(edge?.relationship_type || edge?.relation || "observed-traffic-peer")
    .trim()
    .toLowerCase();
  if (rel === "route_hop" || rel === "route-hop") {
    return "routed-to";
  }
  if (rel === "traffic") {
    return "observed-traffic-peer";
  }
  return rel;
}

function isPublicNodeId(hostId) {
  const node = state.nodes.get(hostId);
  if (!node || !node.host) {
    return false;
  }
  if (node.host.is_external === true) {
    return true;
  }
  const ip = primaryHostIp(node.host);
  return ip ? isPublicIPv4(ip) : false;
}

function mergeRenderableEdge(edgeMap, edge) {
  const a = String(edge.a_host_id || "");
  const b = String(edge.b_host_id || "");
  if (!a || !b || a === b) {
    return;
  }
  const left = a < b ? a : b;
  const right = a < b ? b : a;
  const key = `${left}__${right}`;
  const relation = String(edge.relationship_type || edge.relation || "observed-traffic-peer");
  const confidence = Number.isFinite(Number(edge.confidence)) ? Number(edge.confidence) : 1;
  const count = Number.isFinite(Number(edge.count)) ? Number(edge.count) : 0;

  if (!edgeMap.has(key)) {
    edgeMap.set(key, {
      ...edge,
      a_host_id: left,
      b_host_id: right,
      relation,
      relationship_type: relation,
      confidence,
      count,
      evidence: Array.isArray(edge.evidence) ? [...edge.evidence] : [],
      ports: Array.isArray(edge.ports) ? [...edge.ports] : [],
    });
    return;
  }

  const existing = edgeMap.get(key);
  existing.count += count;
  existing.confidence = Math.max(Number(existing.confidence) || 0, confidence);

  const existingLast = parseTimestamp(existing.last_seen);
  const candidateLast = parseTimestamp(edge.last_seen);
  if (!existingLast || candidateLast > existingLast) {
    existing.last_seen = edge.last_seen || existing.last_seen;
  }

  const existingFirst = parseTimestamp(existing.first_seen);
  const candidateFirst = parseTimestamp(edge.first_seen);
  if (!existingFirst || (candidateFirst && candidateFirst < existingFirst)) {
    existing.first_seen = edge.first_seen || existing.first_seen;
  }

  const existingRelation = edgeRelationship(existing);
  const candidateRelation = edgeRelationship(edge);
  if (candidateRelation === "upstream/external" && existingRelation !== "upstream/external") {
    existing.relation = "upstream/external";
    existing.relationship_type = "upstream/external";
  }
}

function treeRoutedEdges(edges) {
  const gatewayId = state.treeGatewayId;
  if (!gatewayId || !state.nodes.has(gatewayId) || !Array.isArray(edges) || edges.length === 0) {
    return edges;
  }

  const edgeMap = new Map();
  for (const edge of edges) {
    const aPublic = isPublicNodeId(edge.a_host_id);
    const bPublic = isPublicNodeId(edge.b_host_id);

    if (aPublic === bPublic) {
      mergeRenderableEdge(edgeMap, edge);
      continue;
    }

    const publicId = aPublic ? edge.a_host_id : edge.b_host_id;
    const internalId = aPublic ? edge.b_host_id : edge.a_host_id;

    if (!publicId || !internalId) {
      mergeRenderableEdge(edgeMap, edge);
      continue;
    }

    if (internalId === gatewayId) {
      mergeRenderableEdge(edgeMap, {
        ...edge,
        relation: "upstream/external",
        relationship_type: "upstream/external",
      });
      continue;
    }

    mergeRenderableEdge(edgeMap, {
      ...edge,
      a_host_id: gatewayId,
      b_host_id: publicId,
      relation: "upstream/external",
      relationship_type: "upstream/external",
      inferred: true,
      confidence: Math.max(0.62, Number(edge.confidence) || 0),
      evidence: [...(Array.isArray(edge.evidence) ? edge.evidence : []), "tree-gateway-route"],
    });
  }

  return [...edgeMap.values()];
}

function buildTreeLayoutTargets(nodes, edges, width, height) {
  const targets = new Map();
  if (!Array.isArray(nodes) || nodes.length === 0) {
    state.treeGatewayId = null;
    state.treeExternalNodeIds = new Set();
    return targets;
  }

  const nodeById = new Map(nodes.map((node) => [node.host.host_id, node]));
  const ids = nodes.map((node) => node.host.host_id);
  const externalIds = ids.filter((id) => {
    const ip = primaryHostIp(nodeById.get(id)?.host);
    const explicitExternal = nodeById.get(id)?.host?.is_external === true;
    return explicitExternal || (ip ? isPublicIPv4(ip) : false);
  });
  const externalIdSet = new Set(externalIds);
  state.treeExternalNodeIds = new Set(externalIds);
  const internalIds = ids.filter((id) => !externalIdSet.has(id));
  const routerIds = ids.filter((id) => {
    if (externalIdSet.has(id)) {
      return false;
    }
    const role = canonicalNodeRole(nodeById.get(id)?.host);
    return role === "router" || role === "switch";
  });

  const localNode = nodes.find((node) => isLocalHost(node.host)) || null;
  const localNodeId = localNode ? localNode.host.host_id : null;

  let gatewayId = null;
  if (localNodeId) {
    const candidates = edges
      .filter((edge) => {
        const rel = edgeRelationship(edge);
        return rel === "gateway-for" || rel === "routed-to" || rel === "same-segment-peer";
      })
      .map((edge) => (edge.a_host_id === localNodeId ? edge.b_host_id : edge.a_host_id))
      .filter((id) => id && id !== localNodeId && routerIds.includes(id));
    if (candidates.length > 0) {
      candidates.sort((left, right) => {
        const leftNode = nodeById.get(left);
        const rightNode = nodeById.get(right);
        const leftScore = (leftNode?.degree || 0) + (leftNode?.host?.node_role_confidence || 0);
        const rightScore = (rightNode?.degree || 0) + (rightNode?.host?.node_role_confidence || 0);
        return rightScore - leftScore;
      });
      gatewayId = candidates[0];
    }
  }
  if (!gatewayId && routerIds.length > 0) {
    const rankedRouters = routerIds.slice().sort((left, right) => {
      const leftNode = nodeById.get(left);
      const rightNode = nodeById.get(right);
      const leftPrivate = isPrivateIPv4(primaryHostIp(leftNode?.host) || "");
      const rightPrivate = isPrivateIPv4(primaryHostIp(rightNode?.host) || "");
      const leftScore = (leftNode?.degree || 0) + (leftNode?.host?.node_role_confidence || 0) + (leftPrivate ? 0.5 : 0);
      const rightScore = (rightNode?.degree || 0) + (rightNode?.host?.node_role_confidence || 0) + (rightPrivate ? 0.5 : 0);
      return rightScore - leftScore;
    });
    gatewayId = rankedRouters[0] || null;
  }
  state.treeGatewayId = gatewayId;

  const parentById = new Map();
  for (const id of internalIds) {
    const host = nodeById.get(id)?.host;
    const candidate = host?.parent_candidate ? String(host.parent_candidate) : null;
    if (candidate && candidate !== id && nodeById.has(candidate) && !externalIdSet.has(candidate)) {
      parentById.set(id, candidate);
    }
  }

  for (const id of internalIds) {
    if (parentById.has(id)) {
      continue;
    }

    const node = nodeById.get(id);
    if (!node) {
      continue;
    }
    const host = node.host;
    const ip = primaryHostIp(host);
    const isPublic = ip ? isPublicIPv4(ip) : false;
    const role = canonicalNodeRole(host);

    if (isPublic) {
      continue;
    }

    if (id === gatewayId) {
      continue;
    }

    if ((role === "router" || role === "switch") && gatewayId && gatewayId !== id) {
      parentById.set(id, gatewayId);
      continue;
    }

    if (gatewayId && gatewayId !== id) {
      parentById.set(id, gatewayId);
    }
  }

  // Break accidental cycles conservatively.
  for (const id of internalIds) {
    let current = id;
    const seen = new Set([id]);
    while (parentById.has(current)) {
      const parent = parentById.get(current);
      if (!parent || !nodeById.has(parent) || externalIdSet.has(parent)) {
        break;
      }
      if (seen.has(parent)) {
        parentById.delete(current);
        break;
      }
      seen.add(parent);
      current = parent;
    }
  }

  const layerById = new Map();
  const computeLayer = (id, stack = new Set()) => {
    if (layerById.has(id)) {
      return layerById.get(id);
    }
    if (stack.has(id)) {
      layerById.set(id, 3);
      return 3;
    }
    stack.add(id);

    const host = nodeById.get(id)?.host;
    const explicitLayer = Number.isInteger(host?.topology_layer) ? Number(host.topology_layer) : null;
    const parentId = parentById.get(id);
    let layer = 0;
    if (parentId && nodeById.has(parentId) && !externalIdSet.has(parentId)) {
      layer = computeLayer(parentId, stack) + 1;
    } else {
      const ip = primaryHostIp(host);
      if (ip && isPublicIPv4(ip)) {
        layer = 0;
      } else if (id === gatewayId) {
        layer = 1;
      } else if (canonicalNodeRole(host) === "router" || canonicalNodeRole(host) === "switch") {
        layer = 2;
      } else {
        layer = 3;
      }
    }
    if (Number.isInteger(explicitLayer)) {
      layer = Math.max(layer, explicitLayer);
    }
    layerById.set(id, layer);
    stack.delete(id);
    return layer;
  };
  for (const id of internalIds) {
    computeLayer(id);
  }
  for (const id of externalIds) {
    layerById.set(id, 0);
  }

  const childrenById = new Map(internalIds.map((id) => [id, []]));
  for (const [childId, parentId] of parentById.entries()) {
    if (externalIdSet.has(childId) || externalIdSet.has(parentId)) {
      continue;
    }
    if (!childrenById.has(parentId)) {
      childrenById.set(parentId, []);
    }
    childrenById.get(parentId).push(childId);
  }
  for (const [parentId, childIds] of childrenById.entries()) {
    childIds.sort((left, right) => {
      const leftNode = nodeById.get(left);
      const rightNode = nodeById.get(right);
      return nodeSortScore(leftNode).localeCompare(nodeSortScore(rightNode));
    });
    childrenById.set(parentId, childIds);
  }

  const roots = internalIds.filter((id) => !parentById.has(id) || externalIdSet.has(parentById.get(id)));
  if (roots.length === 0 && internalIds.length > 0) {
    if (gatewayId && internalIds.includes(gatewayId)) {
      roots.push(gatewayId);
    } else {
      roots.push(internalIds[0]);
    }
  }
  roots.sort((left, right) => {
    const leftLayer = layerById.get(left) ?? 99;
    const rightLayer = layerById.get(right) ?? 99;
    if (leftLayer !== rightLayer) {
      return leftLayer - rightLayer;
    }
    return nodeSortScore(nodeById.get(left)).localeCompare(nodeSortScore(nodeById.get(right)));
  });

  const leafCountCache = new Map();
  const leafCount = (id) => {
    if (leafCountCache.has(id)) {
      return leafCountCache.get(id);
    }
    const children = childrenById.get(id) || [];
    if (children.length === 0) {
      leafCountCache.set(id, 1);
      return 1;
    }
    let total = 0;
    for (const child of children) {
      total += leafCount(child);
    }
    const safeTotal = Math.max(1, total);
    leafCountCache.set(id, safeTotal);
    return safeTotal;
  };

  const totalLeaves = Math.max(1, roots.reduce((sum, id) => sum + leafCount(id), 0));
  const leftPadding = Math.max(72, width * 0.07);
  const rightPadding = Math.max(72, width * 0.07);
  const topPadding = Math.max(62, height * 0.1);
  const bottomPadding = Math.max(68, height * 0.1);
  const usableWidth = Math.max(1, width - leftPadding - rightPadding);
  const maxLayer = Math.max(1, ...internalIds.map((id) => layerById.get(id) ?? 1));
  const layerGap = Math.max(64, (height - topPadding - bottomPadding) / Math.max(1, maxLayer));
  const leafStep = usableWidth / totalLeaves;
  let leafCursor = 0;

  const yForLayer = (layer) => topPadding + clamp(layer, 0, maxLayer + 1) * layerGap;

  const placeSubtree = (id) => {
    const children = childrenById.get(id) || [];
    let x = leftPadding + (leafCursor + 0.5) * leafStep;
    if (children.length === 0) {
      leafCursor += 1;
    } else {
      const childXs = children.map((childId) => placeSubtree(childId));
      x = childXs.reduce((sum, value) => sum + value, 0) / childXs.length;
    }

    targets.set(id, {
      x,
      y: yForLayer(layerById.get(id) ?? 0),
    });
    return x;
  };

  for (const rootId of roots) {
    placeSubtree(rootId);
  }

  for (const id of internalIds) {
    if (targets.has(id)) {
      continue;
    }
    targets.set(id, {
      x: leftPadding + (stableUnitFromString(id) * usableWidth),
      y: yForLayer(layerById.get(id) ?? (maxLayer + 1)),
    });
  }

  // Place external/public nodes in a wide adaptive top region. This reflows
  // as public-host count changes so nodes can spread out and reduce overlap.
  const gatewayTarget = gatewayId && targets.has(gatewayId) ? targets.get(gatewayId) : null;
  const blobCenterX = gatewayTarget ? gatewayTarget.x : width / 2;

  const sortedExternalIds = externalIds
    .slice()
    .sort((left, right) => stableUnitFromString(left) - stableUnitFromString(right));

  if (sortedExternalIds.length > 0) {
    const count = sortedExternalIds.length;
    const bandTop = 14;
    const bandBottom = clamp(
      Math.min(height * 0.42, Math.max(yForLayer(1) - 34, bandTop + 120)),
      bandTop + 72,
      Math.max(bandTop + 72, height - 90),
    );
    const bandLeft = leftPadding;
    const bandRight = width - rightPadding;
    const blobCenterY = (bandTop + bandBottom) * 0.5;
    const radiusX = Math.max(110, (bandRight - bandLeft) * 0.47);
    const radiusY = Math.max(46, (bandBottom - bandTop) * 0.48);
    const centerX = clamp(blobCenterX, bandLeft + 32, bandRight - 32);
    const area = Math.PI * radiusX * radiusY;
    const minGap = clamp(Math.sqrt(area / Math.max(1, count)) * 0.72, 26, 62);
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));

    const points = sortedExternalIds.map((id, index) => {
      const t = (index + 0.5) / count;
      const radial = Math.sqrt(t);
      const theta = index * goldenAngle;
      return {
        id,
        x: centerX + Math.cos(theta) * radial * radiusX,
        y: blobCenterY + Math.sin(theta) * radial * radiusY,
      };
    });

    // Lightweight relax pass to spread nodes apart and reduce overlap.
    for (let iter = 0; iter < 20; iter += 1) {
      for (let i = 0; i < points.length; i += 1) {
        for (let j = i + 1; j < points.length; j += 1) {
          const a = points[i];
          const b = points[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 0.001;
          if (dist >= minGap) {
            continue;
          }
          const push = (minGap - dist) * 0.5;
          const ux = dx / dist;
          const uy = dy / dist;
          a.x += ux * push;
          b.x -= ux * push;
          a.y += uy * push;
          b.y -= uy * push;
        }
      }

      for (const point of points) {
        const ex = (point.x - centerX) / radiusX;
        const ey = (point.y - blobCenterY) / radiusY;
        const er = Math.sqrt(ex * ex + ey * ey);
        if (er > 1) {
          point.x = centerX + (ex / er) * radiusX;
          point.y = blobCenterY + (ey / er) * radiusY;
        }
        point.x = clamp(point.x, bandLeft, bandRight);
        point.y = clamp(point.y, bandTop, bandBottom);
      }
    }

    for (const point of points) {
      targets.set(point.id, { x: point.x, y: point.y });
    }
  }

  return targets;
}

function zoomPercentToScale(percent) {
  const p = clamp(percent, 0, 100);
  if (p >= DEFAULT_ZOOM_PERCENT) {
    const t = (p - DEFAULT_ZOOM_PERCENT) / (100 - DEFAULT_ZOOM_PERCENT);
    return 1 + t * 1.05;
  }
  const t = (DEFAULT_ZOOM_PERCENT - p) / DEFAULT_ZOOM_PERCENT;
  return 1 - t * 0.45;
}

function zoomPercentToCameraDistance(percent) {
  const p = clamp(percent, 0, 100);
  if (p >= DEFAULT_ZOOM_PERCENT) {
    const t = (p - DEFAULT_ZOOM_PERCENT) / (100 - DEFAULT_ZOOM_PERCENT);
    return CAMERA_ZOOM_DEFAULT_DISTANCE - t * (CAMERA_ZOOM_DEFAULT_DISTANCE - CAMERA_ZOOM_MIN_DISTANCE);
  }
  const t = (DEFAULT_ZOOM_PERCENT - p) / DEFAULT_ZOOM_PERCENT;
  return CAMERA_ZOOM_DEFAULT_DISTANCE + t * (CAMERA_ZOOM_MAX_DISTANCE - CAMERA_ZOOM_DEFAULT_DISTANCE);
}

function cameraDistanceToZoomPercent(distance) {
  const d = clamp(distance, CAMERA_ZOOM_MIN_DISTANCE, CAMERA_ZOOM_MAX_DISTANCE);
  if (d <= CAMERA_ZOOM_DEFAULT_DISTANCE) {
    const t = (CAMERA_ZOOM_DEFAULT_DISTANCE - d) / (CAMERA_ZOOM_DEFAULT_DISTANCE - CAMERA_ZOOM_MIN_DISTANCE);
    return DEFAULT_ZOOM_PERCENT + t * (100 - DEFAULT_ZOOM_PERCENT);
  }
  const t = (d - CAMERA_ZOOM_DEFAULT_DISTANCE) / (CAMERA_ZOOM_MAX_DISTANCE - CAMERA_ZOOM_DEFAULT_DISTANCE);
  return DEFAULT_ZOOM_PERCENT - t * DEFAULT_ZOOM_PERCENT;
}

function updateZoomSliderVisual() {
  const percent = clamp(state.zoomPercent, 0, 100);
  zoomSlider.value = String(Math.round(percent));
  zoomSliderFill.style.height = `${percent}%`;
}

function applyZoomPercent(percent, options = {}) {
  const p = clamp(percent, 0, 100);
  const syncCamera = options.syncCamera !== false;
  state.zoomPercent = p;
  if (syncCamera) {
    state.camera.distance = clamp(
      zoomPercentToCameraDistance(p),
      CAMERA_ZOOM_MIN_DISTANCE,
      2100,
    );
  }
  updateZoomSliderVisual();
}

function syncZoomFromCameraDistance() {
  const percent = cameraDistanceToZoomPercent(state.camera.distance);
  applyZoomPercent(percent, { syncCamera: false });
}

function applyScreenZoom(projected) {
  const zoomScale = zoomPercentToScale(state.zoomPercent);
  if (!projected) {
    return null;
  }
  const cx = state.width / 2;
  const cy = state.height / 2;
  return {
    ...projected,
    x: cx + (projected.x - cx) * zoomScale,
    y: cy + (projected.y - cy) * zoomScale,
    scale: (projected.scale || 1) * Math.sqrt(zoomScale),
  };
}

function apply2DPan(projected) {
  if (!projected) {
    return null;
  }
  if (state.mode !== "2d") {
    return projected;
  }
  return {
    ...projected,
    x: projected.x + state.view2d.offsetX,
    y: projected.y + state.view2d.offsetY,
  };
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
    return "2D mode shows active topology layout optimized for analysis. Drag to pan.";
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

function updateHostFilterLabel() {
  hostFilterButton.textContent = `Hosts: ${HOST_FILTER_LABELS[state.hostFilter]}`;
}

function updateTopologyLayoutLabel() {
  topologyLayoutButton.textContent = `Topology: ${TOPOLOGY_LAYOUT_LABELS[state.topologyLayoutMode]}`;
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

function setSettingsTab(tabName) {
  state.settingsTab = tabName === "data" ? "data" : "display";
  const displayActive = state.settingsTab === "display";

  settingsTabDisplayButton.classList.toggle("is-active", displayActive);
  settingsTabDataButton.classList.toggle("is-active", !displayActive);
  settingsTabDisplayButton.setAttribute("aria-selected", displayActive ? "true" : "false");
  settingsTabDataButton.setAttribute("aria-selected", displayActive ? "false" : "true");
  settingsPanelDisplay.classList.toggle("is-active", displayActive);
  settingsPanelData.classList.toggle("is-active", !displayActive);

  if (!displayActive) {
    renderTopologyTextList(state.lastSnapshot);
  }
}

function updateStaleThresholdFieldState() {
  const enabled = Boolean(hideStaleToggle.checked);
  keepStalePrivateToggle.disabled = !enabled;
  staleThresholdInput.disabled = !enabled;
  keepStalePrivateField.classList.toggle("is-disabled", !enabled);
  staleThresholdField.classList.toggle("is-disabled", !enabled);
  staleDependentOptions.classList.toggle("is-disabled", !enabled);
}

function updateActiveScopeFieldState() {
  const enabled = Boolean(activeSensorToggle.checked);
  activeIcmpToggle.disabled = !enabled;
  activeNmapToggle.disabled = !enabled;
  activeScopeAllToggle.disabled = !enabled;
  activeIcmpField.classList.toggle("is-disabled", !enabled);
  activeNmapField.classList.toggle("is-disabled", !enabled);
  activeScopeAllField.classList.toggle("is-disabled", !enabled);
}

function syncSettingsInputsFromState() {
  activeSensorToggle.checked = state.activeSensorEnabled;
  activeIcmpToggle.checked = state.activeIcmpScanEnabled;
  activeNmapToggle.checked = state.activeNmapScanEnabled;
  activeScopeAllToggle.checked = state.allowAllActiveTargetsEnabled;
  hideStaleToggle.checked = state.hideStaleHostsEnabled;
  keepStalePrivateToggle.checked = state.keepStalePrivateHostsEnabled;
  staleThresholdInput.value = String(state.staleHostThresholdSeconds);
  refreshIntervalInput.value = String(state.refreshIntervalMs);
  hostLimitInput.value = String(state.hostLimit);
  edgeLimitInput.value = String(state.edgeLimit);
  updateActiveScopeFieldState();
  updateStaleThresholdFieldState();
}

function openSettingsDrawer() {
  syncSettingsInputsFromState();
  setSettingsTab(state.settingsTab);
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

function formatServices(services) {
  if (!Array.isArray(services) || services.length === 0) {
    return "None";
  }

  const formatted = services
    .slice(0, 10)
    .map((entry) => {
      if (!Array.isArray(entry) || entry.length < 3) {
        return escapeHtml(String(entry));
      }
      const proto = escapeHtml(entry[0] || "");
      const port = escapeHtml(entry[1] || "");
      const service = escapeHtml(entry[2] || "unknown");
      const product = escapeHtml(entry[3] || "");
      const version = escapeHtml(entry[4] || "");
      const detail = [product, version].filter(Boolean).join(" ");
      return `${proto}/${port} ${service}${detail ? ` (${detail})` : ""}`;
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

function formatAgeText(value) {
  const age = ageSeconds(value);
  if (!Number.isFinite(age)) {
    return "Unknown";
  }
  return `${Math.round(age)}s ago`;
}

function formatSimpleList(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return "None";
  }
  return values.join(", ");
}

function formatEdgePortList(ports) {
  if (!Array.isArray(ports) || ports.length === 0) {
    return "None";
  }
  return ports
    .slice(0, 12)
    .map((entry) => (Array.isArray(entry) ? entry.join("/") : String(entry)))
    .join(", ");
}

function renderTopologyTextList(snapshot) {
  if (!topologyTextList) {
    return;
  }
  if (!snapshot || typeof snapshot !== "object") {
    topologyTextList.textContent = "No topology data yet.";
    return;
  }

  const hosts = Array.isArray(snapshot.hosts) ? snapshot.hosts.map(normalizeHost) : [];
  const validHosts = hosts.filter((host) => host.host_id);
  const hostIds = new Set(validHosts.map((host) => host.host_id));
  const edges = Array.isArray(snapshot.edges) ? snapshot.edges.map(normalizeEdge) : [];
  const validEdges = edges.filter(
    (edge) => hostIds.has(edge.a_host_id) && hostIds.has(edge.b_host_id),
  );

  const sortedHosts = validHosts
    .slice()
    .sort((left, right) => parseTimestamp(right.last_seen) - parseTimestamp(left.last_seen));
  const sortedEdges = validEdges
    .slice()
    .sort((left, right) => parseTimestamp(right.last_seen) - parseTimestamp(left.last_seen));

  const lines = [];
  const capturedAt = snapshot.captured_at ? new Date(snapshot.captured_at).toLocaleString() : "Unknown";
  lines.push(`Captured: ${capturedAt}`);
  lines.push(`Map Visible: ${state.nodes.size} hosts, ${state.edges.length} edges`);
  lines.push(`Snapshot Total: ${validHosts.length} hosts, ${validEdges.length} edges`);
  lines.push("");
  lines.push("HOSTS");

  if (sortedHosts.length === 0) {
    lines.push("(none)");
  } else {
    sortedHosts.forEach((host, index) => {
      const localLabel = isLocalHost(host) ? " [LOCAL]" : "";
      lines.push(`${index + 1}. ${host.host_id}${localLabel}`);
      lines.push(`   IPs: ${formatSimpleList(host.ips)}`);
      lines.push(`   MACs: ${formatSimpleList(host.macs)}`);
      const roleLabel = host.role ? `${host.role} (${Math.round((host.role_confidence || 0) * 100)}%)` : "Unknown";
      const nodeRoleLabel = host.node_role
        ? `${host.node_role} (${Math.round((host.node_role_confidence || 0) * 100)}%)`
        : "Unknown";
      lines.push(`   Vendor: ${host.vendor || "Unknown"} | OS: ${host.os_guess || "Unknown"}`);
      lines.push(`   Detailed Role: ${roleLabel} | Topology Role: ${nodeRoleLabel}`);
      lines.push(`   Parent: ${host.parent_candidate || "None"} (${Number.isFinite(host.parent_confidence) ? `${Math.round(host.parent_confidence * 100)}%` : "n/a"}) | Layer: ${Number.isInteger(host.topology_layer) ? host.topology_layer : "n/a"}`);
      lines.push(`   First Seen: ${formatTime(host.first_seen)}`);
      lines.push(`   Last Seen: ${formatTime(host.last_seen)} (${formatAgeText(host.last_seen)})`);
      lines.push("");
    });
  }

  lines.push("EDGES");
  if (sortedEdges.length === 0) {
    lines.push("(none)");
  } else {
    sortedEdges.forEach((edge, index) => {
      const proto = edge.proto || "unknown";
      const relation = edge.relationship_type || edge.relation || "observed-traffic-peer";
      const confidenceText = Number.isFinite(edge.confidence) ? `${Math.round(edge.confidence * 100)}%` : "n/a";
      lines.push(`${index + 1}. ${edge.a_host_id} <-> ${edge.b_host_id}`);
      lines.push(`   Proto: ${proto} | Relation: ${relation} | Confidence: ${confidenceText} | Count: ${edge.count} | Last Seen: ${formatAgeText(edge.last_seen)}`);
      lines.push(`   Ports: ${formatEdgePortList(edge.ports)}`);
      lines.push("");
    });
  }

  topologyTextList.textContent = lines.join("\n").trimEnd();
}

function renderHostDetails(host) {
  hostDetailsElement.innerHTML = `
    <div class="detail-row"><span>Host ID</span><strong>${escapeHtml(host.host_id)}</strong></div>
    <div class="detail-row"><span>IPs</span><strong>${formatArray(host.ips)}</strong></div>
    <div class="detail-row"><span>MACs</span><strong>${formatArray(host.macs)}</strong></div>
    <div class="detail-row"><span>Hostnames</span><strong>${formatArray(host.hostnames)}</strong></div>
    <div class="detail-row"><span>Vendor</span><strong>${escapeHtml(host.vendor || "Unknown")}</strong></div>
    <div class="detail-row"><span>OS Guess</span><strong>${escapeHtml(host.os_guess || "Unknown")}</strong></div>
    <div class="detail-row"><span>Detailed Role</span><strong>${escapeHtml(host.role || "Unknown")}</strong></div>
    <div class="detail-row"><span>Detailed Role Confidence</span><strong>${Number.isFinite(host.role_confidence) ? `${Math.round(host.role_confidence * 100)}%` : "Unknown"}</strong></div>
    <div class="detail-row"><span>Topology Role</span><strong>${escapeHtml(host.node_role || "Unknown")}</strong></div>
    <div class="detail-row"><span>Topology Role Confidence</span><strong>${Number.isFinite(host.node_role_confidence) ? `${Math.round(host.node_role_confidence * 100)}%` : "Unknown"}</strong></div>
    <div class="detail-row"><span>Parent Candidate</span><strong>${escapeHtml(host.parent_candidate || "None")}</strong></div>
    <div class="detail-row"><span>Parent Confidence</span><strong>${Number.isFinite(host.parent_confidence) ? `${Math.round(host.parent_confidence * 100)}%` : "Unknown"}</strong></div>
    <div class="detail-row"><span>Topology Layer</span><strong>${Number.isInteger(host.topology_layer) ? host.topology_layer : "Unknown"}</strong></div>
    <div class="detail-row"><span>First Seen</span><strong>${escapeHtml(formatTime(host.first_seen))}</strong></div>
    <div class="detail-row"><span>Last Seen</span><strong>${escapeHtml(formatTime(host.last_seen))}</strong></div>
    <div class="detail-row"><span>Ports</span><strong>${formatPorts(host.ports)}</strong></div>
    <div class="detail-row"><span>Services</span><strong>${formatServices(host.services)}</strong></div>
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
    hostnames: Array.isArray(raw.hostnames) ? raw.hostnames.filter(Boolean).map(String) : [],
    vendor: raw.vendor ? String(raw.vendor) : null,
    os_guess: raw.os_guess ? String(raw.os_guess) : null,
    role: raw.role ? String(raw.role) : null,
    role_confidence: Number.isFinite(Number(raw.role_confidence)) ? Number(raw.role_confidence) : null,
    role_scores: raw.role_scores && typeof raw.role_scores === "object" ? raw.role_scores : {},
    node_role: raw.node_role ? String(raw.node_role) : null,
    node_role_confidence: Number.isFinite(Number(raw.node_role_confidence))
      ? Number(raw.node_role_confidence)
      : null,
    parent_candidate: raw.parent_candidate ? String(raw.parent_candidate) : null,
    parent_confidence: Number.isFinite(Number(raw.parent_confidence)) ? Number(raw.parent_confidence) : null,
    topology_layer: Number.isInteger(Number(raw.topology_layer)) ? Number(raw.topology_layer) : null,
    is_external: typeof raw.is_external === "boolean" ? raw.is_external : null,
    first_seen: raw.first_seen ? String(raw.first_seen) : null,
    last_seen: raw.last_seen ? String(raw.last_seen) : null,
    ports: Array.isArray(raw.ports) ? raw.ports : [],
    services: Array.isArray(raw.services) ? raw.services : [],
  };
}

function normalizeEdge(raw) {
  return {
    edge_key: String(raw.edge_key || ""),
    a_host_id: String(raw.a_host_id || ""),
    b_host_id: String(raw.b_host_id || ""),
    proto: raw.proto ? String(raw.proto) : "",
    relation: raw.relationship_type
      ? String(raw.relationship_type)
      : (raw.relation ? String(raw.relation) : "observed-traffic-peer"),
    relationship_type: raw.relationship_type ? String(raw.relationship_type) : null,
    inferred: Boolean(raw.inferred),
    confidence: Number.isFinite(Number(raw.confidence)) ? Number(raw.confidence) : 1,
    evidence: Array.isArray(raw.evidence) ? raw.evidence : [],
    first_seen: raw.first_seen ? String(raw.first_seen) : null,
    last_seen: raw.last_seen ? String(raw.last_seen) : null,
    count: Number.isFinite(Number(raw.count)) ? Number(raw.count) : 0,
    ports: Array.isArray(raw.ports) ? raw.ports : [],
  };
}

function applySnapshot(snapshot) {
  state.lastSnapshot = snapshot;
  const hosts = Array.isArray(snapshot.hosts) ? snapshot.hosts.map(normalizeHost) : [];
  const edges = Array.isArray(snapshot.edges) ? snapshot.edges.map(normalizeEdge) : [];

  const validHosts = hosts.filter((host) => host.host_id);
  const visibleHosts = validHosts.filter((host) => hostShouldRender(host));
  const allHostIds = new Set(validHosts.map((host) => host.host_id));
  const visibleNodeIds = new Set(visibleHosts.map((host) => host.host_id));
  const centerX = state.width / 2;
  const centerY = state.height / 2;

  for (const host of visibleHosts) {
    const node = ensureNode(host);
    if (isLocalHost(host)) {
      node.x = centerX;
      node.y = centerY;
      node.vx *= 0.35;
      node.vy *= 0.35;
    }
  }

  for (const existingId of [...state.nodes.keys()]) {
    if (!visibleNodeIds.has(existingId)) {
      state.nodes.delete(existingId);
    }
  }

  const degreeMap = new Map();
  const allValidEdges = edges.filter(
    (edge) => allHostIds.has(edge.a_host_id) && allHostIds.has(edge.b_host_id),
  );
  const validEdges = allValidEdges.filter(
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
  countsStatusElement.textContent = `Hosts: ${visibleHosts.length}/${validHosts.length} | Edges: ${validEdges.length}/${allValidEdges.length}`;
  updatedStatusElement.textContent = `Last update: ${lastUpdate}`;
  canvasEmpty.classList.toggle("is-hidden", visibleHosts.length > 0);
  renderTopologyTextList(snapshot);
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

function drawLocalHostStar(cx, cy, outerRadius, scale = 1) {
  const spikes = 5;
  const innerRadius = Math.max(outerRadius * 0.74, outerRadius - 6.5);
  const step = Math.PI / spikes;
  let angle = -Math.PI / 2;
  const points = [];

  for (let i = 0; i < spikes * 2; i += 1) {
    const radius = i % 2 === 0 ? outerRadius : innerRadius;
    points.push({
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    });
    angle += step;
  }

  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.98)";
  ctx.lineWidth = clamp(1.5 * scale, 1.1, 2.7);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.shadowColor = "rgba(255, 255, 255, 0.35)";
  ctx.shadowBlur = clamp(4.5 * scale, 2.5, 8.5);

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
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

function drawNodeRoleGlyph2D(host, x, y, radius) {
  const drawRoundedRect = (rx, ry, rw, rh, rr) => {
    if (typeof ctx.roundRect === "function") {
      ctx.roundRect(rx, ry, rw, rh, rr);
      return;
    }
    const r = Math.min(rr, rw / 2, rh / 2);
    ctx.moveTo(rx + r, ry);
    ctx.lineTo(rx + rw - r, ry);
    ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + r);
    ctx.lineTo(rx + rw, ry + rh - r);
    ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - r, ry + rh);
    ctx.lineTo(rx + r, ry + rh);
    ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - r);
    ctx.lineTo(rx, ry + r);
    ctx.quadraticCurveTo(rx, ry, rx + r, ry);
  };

  const role = canonicalNodeRole(host);
  const glyphColor = "rgba(243, 248, 255, 0.94)";
  const strokeColor = "rgba(10, 12, 18, 0.65)";
  const s = Math.max(6, radius * 0.7);

  ctx.save();
  ctx.strokeStyle = strokeColor;
  ctx.fillStyle = glyphColor;
  ctx.lineWidth = Math.max(1.2, radius * 0.13);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  if (role === "router") {
    ctx.beginPath();
    ctx.arc(x, y, s * 0.62, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - s * 0.95, y);
    ctx.lineTo(x - s * 0.5, y);
    ctx.moveTo(x + s * 0.5, y);
    ctx.lineTo(x + s * 0.95, y);
    ctx.moveTo(x, y - s * 0.95);
    ctx.lineTo(x, y - s * 0.5);
    ctx.moveTo(x, y + s * 0.5);
    ctx.lineTo(x, y + s * 0.95);
    ctx.stroke();
  } else if (role === "switch") {
    const w = s * 1.55;
    const h = s * 0.92;
    const rx = x - w / 2;
    const ry = y - h / 2;
    ctx.beginPath();
    drawRoundedRect(rx, ry, w, h, Math.max(2, h * 0.2));
    ctx.stroke();
    const portCount = 4;
    for (let i = 0; i < portCount; i += 1) {
      const px = rx + (w * (i + 1)) / (portCount + 1);
      const py = ry + h * 0.62;
      ctx.beginPath();
      ctx.arc(px, py, Math.max(1.1, s * 0.08), 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (role === "server") {
    const w = s * 1.2;
    const h = s * 0.42;
    for (let i = 0; i < 3; i += 1) {
      const ry = y - h * 1.35 + i * h * 1.35;
      ctx.beginPath();
      drawRoundedRect(x - w / 2, ry, w, h, Math.max(2, h * 0.25));
      ctx.stroke();
    }
  } else if (role === "workstation") {
    const w = s * 1.3;
    const h = s * 0.84;
    ctx.beginPath();
    drawRoundedRect(x - w / 2, y - h * 0.72, w, h, Math.max(2, h * 0.18));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - w * 0.2, y + h * 0.25);
    ctx.lineTo(x + w * 0.2, y + h * 0.25);
    ctx.moveTo(x, y + h * 0.25);
    ctx.lineTo(x, y + h * 0.5);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(x, y - s * 0.74);
    ctx.lineTo(x + s * 0.74, y);
    ctx.lineTo(x, y + s * 0.74);
    ctx.lineTo(x - s * 0.74, y);
    ctx.closePath();
    ctx.stroke();
    ctx.fillStyle = "rgba(243, 248, 255, 0.8)";
    ctx.beginPath();
    ctx.arc(x, y, Math.max(1.7, s * 0.08), 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function drawNodesAndEdges2D(projectionForNode) {
  const projections = new Map();
  state.hitRegions = [];
  for (const [hostId, node] of state.nodes.entries()) {
    projections.set(hostId, apply2DPan(applyScreenZoom(projectionForNode(node))));
  }
  const edgesToRender = (state.mode === "2d" && state.topologyLayoutMode === "tree")
    ? treeRoutedEdges(state.edges)
    : state.edges;

  ctx.save();
  ctx.lineCap = "round";
  for (const edge of edgesToRender) {
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
    const isLocal = isLocalHost(node.host);

    ctx.beginPath();
    ctx.fillStyle = "rgba(5, 7, 11, 0.45)";
    ctx.arc(x + 2, y + 2, radius + 0.7, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.fillStyle = hostRecencyColor(node.host.last_seen);
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    drawNodeRoleGlyph2D(node.host, x, y, radius);

    if (isLocal) {
      drawLocalHostStar(x, y, radius + 6, projected.scale);
    }

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
    const isLocal = isLocalHost(entry.node.host);
    const hit = drawCube(entry.world, entry.size, entry.height, base, selected);
    if (!hit) {
      continue;
    }

    if (isLocal) {
      drawLocalHostStar(hit.x, hit.y, Math.max(12, hit.radius * 0.92), clamp(hit.radius * 0.08, 0.85, 1.9));
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
  const useTreeLayout = state.topologyLayoutMode === "tree";
  if (useTreeLayout) {
    const targets = buildTreeLayoutTargets(nodes, state.edges, width, height);
    for (const node of nodes) {
      const target = targets.get(node.host.host_id);
      if (!target) {
        continue;
      }
      node.vx = (target.x - node.x) * 0.44;
      node.vy = (target.y - node.y) * 0.44;
      node.x += node.vx;
      node.y += node.vy;
      node.vx *= 0.42;
      node.vy *= 0.42;
      node.z *= 0.92;
      node.vz *= 0.9;
    }
    return;
  }

  const repulsion = state.mode === "idle"
    ? 2600
    : 1900;
  const springStrength = 0.0048;
  const damping = 0.88;
  const attraction = 0.0017;
  const idealEdgeLength = clamp(
    Math.sqrt((width * height) / Math.max(nodes.length, 1)) * 0.85,
    70,
    220,
  );
  const anchors = new Map();
  const localNodeId = (nodes.find((node) => isLocalHost(node.host)) || {}).host?.host_id || null;

  for (let i = 0; i < nodes.length; i += 1) {
    const a = nodes[i];
    const anchorA = anchors.get(a.host.host_id);
    for (let j = i + 1; j < nodes.length; j += 1) {
      const b = nodes[j];
      const anchorB = anchors.get(b.host.host_id);
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = dx * dx + dy * dy + 1.0;
      const dist = Math.sqrt(distSq);
      let force = repulsion / distSq;
      if (anchorA && anchorB && anchorA.tier === anchorB.tier) {
        force *= 0.88;
      }
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
    let targetLength = idealEdgeLength;
    let edgeSpring = springStrength;
    const relation = edgeRelationship(edge);
    if (relation === "routed-to" || relation === "gateway-for") {
      targetLength *= 0.74;
      edgeSpring *= 1.18;
    } else if (relation === "upstream/external") {
      targetLength *= 1.12;
      edgeSpring *= 1.05;
    } else if (relation === "same-segment-peer") {
      targetLength *= 0.9;
      edgeSpring *= 1.08;
    }
    if (edge.inferred) {
      edgeSpring *= 0.9;
    }
    const confidence = Number(edge.confidence);
    if (Number.isFinite(confidence)) {
      edgeSpring *= clamp(confidence, 0.35, 1.15);
    }
    const force = (dist - targetLength) * edgeSpring;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    a.vx += fx;
    a.vy += fy;
    b.vx -= fx;
    b.vy -= fy;
  }

  for (const node of nodes) {
    const hostId = node.host.host_id;
    const isLocal = localNodeId && hostId === localNodeId;
    const anchor = anchors.get(hostId);

    if (anchor) {
      node.vx += (anchor.x - node.x) * anchor.strength;
      node.vy += (anchor.y - node.y) * anchor.strength;
      node.vx += (centerX - node.x) * 0.00032;
      node.vy += (centerY - node.y) * 0.00032;
    } else {
      node.vx += (centerX - node.x) * attraction;
      node.vy += (centerY - node.y) * attraction;
    }

    if (isLocal) {
      const localLockStrength = 0.48;
      node.vx += (centerX - node.x) * localLockStrength;
      node.vy += (centerY - node.y) * localLockStrength;
    }

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

    if (isLocal) {
      node.x = centerX;
      node.y = centerY;
      node.vx *= 0.2;
      node.vy *= 0.2;
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
  if (state.mode === "3d") {
    event.preventDefault();
    state.camera.dragging = true;
    state.camera.dragMode = (event.button === 2 || event.shiftKey || event.altKey) ? "pan" : "orbit";
    state.camera.dragDistance = 0;
    state.camera.pointerId = event.pointerId;
    state.camera.lastX = event.clientX;
    state.camera.lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  if (state.mode !== "2d" || event.button !== 0) {
    return;
  }

  event.preventDefault();
  state.view2d.dragging = true;
  state.view2d.dragDistance = 0;
  state.view2d.pointerId = event.pointerId;
  state.view2d.lastX = event.clientX;
  state.view2d.lastY = event.clientY;
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", (event) => {
  if (state.mode === "3d" && state.camera.dragging) {
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
    return;
  }
  if (state.mode !== "2d" || !state.view2d.dragging) {
    return;
  }

  const dx = event.clientX - state.view2d.lastX;
  const dy = event.clientY - state.view2d.lastY;
  state.view2d.lastX = event.clientX;
  state.view2d.lastY = event.clientY;
  state.view2d.dragDistance += Math.abs(dx) + Math.abs(dy);
  state.view2d.offsetX += dx;
  state.view2d.offsetY += dy;
});

canvas.addEventListener("pointerup", (event) => {
  if (state.camera.pointerId === event.pointerId) {
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    if (state.camera.dragDistance > 4) {
      state.camera.lastDragAt = Date.now();
    }
    state.camera.dragging = false;
    state.camera.dragMode = null;
    state.camera.pointerId = null;
    state.camera.dragDistance = 0;
  }
  if (state.view2d.pointerId === event.pointerId) {
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    if (state.view2d.dragDistance > 4) {
      state.view2d.lastDragAt = Date.now();
    }
    state.view2d.dragging = false;
    state.view2d.pointerId = null;
    state.view2d.dragDistance = 0;
  }
});

canvas.addEventListener("pointercancel", (event) => {
  if (!event || state.camera.pointerId === event.pointerId) {
    state.camera.dragging = false;
    state.camera.dragMode = null;
    state.camera.pointerId = null;
    state.camera.dragDistance = 0;
  }
  if (!event || state.view2d.pointerId === event.pointerId) {
    state.view2d.dragging = false;
    state.view2d.pointerId = null;
    state.view2d.dragDistance = 0;
  }
});

canvas.addEventListener("wheel", (event) => {
  if (state.mode !== "3d") {
    return;
  }

  event.preventDefault();
  state.camera.distance = clamp(state.camera.distance + event.deltaY * 0.45, 420, 2100);
  syncZoomFromCameraDistance();
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
    syncZoomFromCameraDistance();
    event.preventDefault();
    return;
  }
  if (event.key === "-" || event.key === "_") {
    state.camera.distance = clamp(state.camera.distance + zoomStep, 420, 2100);
    syncZoomFromCameraDistance();
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
  if (state.mode === "2d" && Date.now() - state.view2d.lastDragAt < 180) {
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

settingsTabDisplayButton.addEventListener("click", () => {
  setSettingsTab("display");
});

settingsTabDataButton.addEventListener("click", () => {
  setSettingsTab("data");
});

hideStaleToggle.addEventListener("change", () => {
  updateStaleThresholdFieldState();
});

activeSensorToggle.addEventListener("change", () => {
  updateActiveScopeFieldState();
});

activeScopeAllToggle.addEventListener("change", () => {
  if (!activeScopeAllToggle.checked) {
    return;
  }

  const confirmed = window.confirm(
    "Are you sure you want to allow active scanning of public internet IPs?",
  );
  if (!confirmed) {
    activeScopeAllToggle.checked = false;
  }
});

refreshDataListButton.addEventListener("click", () => {
  renderTopologyTextList(state.lastSnapshot);
});

closeDrawerButton.addEventListener("click", () => {
  closeHostDrawer();
});

drawerBackdrop.addEventListener("click", () => {
  closeHostDrawer();
  closeSettingsDrawer();
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const activeSensorEnabled = Boolean(activeSensorToggle.checked);
  const activeIcmpScanEnabled = Boolean(activeIcmpToggle.checked);
  const activeNmapScanEnabled = Boolean(activeNmapToggle.checked);
  const allowAllActiveTargetsEnabled = Boolean(activeScopeAllToggle.checked);
  const hideStaleHostsEnabled = Boolean(hideStaleToggle.checked);
  const keepStalePrivateHostsEnabled = Boolean(keepStalePrivateToggle.checked);
  const staleHostThresholdSeconds = clamp(
    Number.parseInt(staleThresholdInput.value, 10) || 180,
    15,
    7200,
  );
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

  activeSensorToggle.checked = activeSensorEnabled;
  activeIcmpToggle.checked = activeIcmpScanEnabled;
  activeNmapToggle.checked = activeNmapScanEnabled;
  activeScopeAllToggle.checked = allowAllActiveTargetsEnabled;
  hideStaleToggle.checked = hideStaleHostsEnabled;
  keepStalePrivateToggle.checked = keepStalePrivateHostsEnabled;
  staleThresholdInput.value = String(staleHostThresholdSeconds);
  refreshIntervalInput.value = String(refreshInterval);
  hostLimitInput.value = String(hostLimit);
  edgeLimitInput.value = String(edgeLimit);
  updateActiveScopeFieldState();
  updateStaleThresholdFieldState();

  try {
    const runtimeSettings = await window.nettower.updateSessionSettings({
      enable_active_discovery: activeSensorEnabled,
      enable_icmp_scan: activeIcmpScanEnabled,
      enable_nmap_scan: activeNmapScanEnabled,
      allow_all_active_targets: allowAllActiveTargetsEnabled,
    });
    state.activeSensorEnabled = Boolean(runtimeSettings.enable_active_discovery);
    state.activeIcmpScanEnabled = Boolean(runtimeSettings.enable_icmp_scan);
    state.activeNmapScanEnabled = Boolean(runtimeSettings.enable_nmap_scan);
    state.allowAllActiveTargetsEnabled = Boolean(runtimeSettings.allow_all_active_targets);
  } catch (error) {
    setStatus(`Failed to apply active sensor settings: ${error.message}`, "error");
    syncSettingsInputsFromState();
    return;
  }

  state.hideStaleHostsEnabled = hideStaleHostsEnabled;
  state.keepStalePrivateHostsEnabled = keepStalePrivateHostsEnabled;
  state.staleHostThresholdSeconds = staleHostThresholdSeconds;
  state.refreshIntervalMs = refreshInterval;
  state.hostLimit = hostLimit;
  state.edgeLimit = edgeLimit;

  if (state.lastSnapshot) {
    applySnapshot(state.lastSnapshot);
  }

  closeSettingsDrawer();
  restartPolling();
});

modeButton.addEventListener("click", () => {
  const index = MODE_ORDER.indexOf(state.mode);
  const nextIndex = (index + 1) % MODE_ORDER.length;
  state.mode = MODE_ORDER[nextIndex];
  state.camera.dragging = false;
  state.camera.dragMode = null;
  state.camera.pointerId = null;
  state.camera.dragDistance = 0;
  state.view2d.dragging = false;
  state.view2d.pointerId = null;
  state.view2d.dragDistance = 0;
  if (state.mode === "3d") {
    state.camera.distance = clamp(
      zoomPercentToCameraDistance(state.zoomPercent),
      CAMERA_ZOOM_MIN_DISTANCE,
      2100,
    );
  }
  updateModeLabel();
});

zoomSlider.addEventListener("input", () => {
  const value = Number.parseInt(zoomSlider.value, 10);
  applyZoomPercent(Number.isFinite(value) ? value : DEFAULT_ZOOM_PERCENT, { syncCamera: true });
});

hostFilterButton.addEventListener("click", () => {
  const index = HOST_FILTER_ORDER.indexOf(state.hostFilter);
  const nextIndex = (index + 1) % HOST_FILTER_ORDER.length;
  state.hostFilter = HOST_FILTER_ORDER[nextIndex];
  updateHostFilterLabel();

  if (state.lastSnapshot) {
    applySnapshot(state.lastSnapshot);
  }
});

topologyLayoutButton.addEventListener("click", () => {
  const index = TOPOLOGY_LAYOUT_ORDER.indexOf(state.topologyLayoutMode);
  const nextIndex = (index + 1) % TOPOLOGY_LAYOUT_ORDER.length;
  state.topologyLayoutMode = TOPOLOGY_LAYOUT_ORDER[nextIndex];
  updateTopologyLayoutLabel();

  if (state.lastSnapshot) {
    applySnapshot(state.lastSnapshot);
  }
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

async function initialize() {
  try {
    const identity = await window.nettower.getLocalIdentity();
    if (identity && typeof identity === "object") {
      state.localIdentity = {
        interface: identity.interface ? String(identity.interface) : null,
        ip: identity.ip ? String(identity.ip) : null,
        mac: identity.mac ? String(identity.mac) : null,
      };
    }
  } catch {
    state.localIdentity = {
      interface: null,
      ip: null,
      mac: null,
    };
  }

  try {
    const sessionSettings = await window.nettower.getSessionSettings();
    if (sessionSettings && typeof sessionSettings === "object") {
      state.activeSensorEnabled = Boolean(sessionSettings.enable_active_discovery);
      state.activeIcmpScanEnabled = Boolean(sessionSettings.enable_icmp_scan);
      state.activeNmapScanEnabled = Boolean(sessionSettings.enable_nmap_scan);
      state.allowAllActiveTargetsEnabled = Boolean(sessionSettings.allow_all_active_targets);
    }
  } catch {
    state.activeSensorEnabled = false;
    state.activeIcmpScanEnabled = true;
    state.activeNmapScanEnabled = true;
    state.allowAllActiveTargetsEnabled = false;
  }

  applyZoomPercent(DEFAULT_ZOOM_PERCENT, { syncCamera: true });
  updateModeLabel();
  updateHostFilterLabel();
  updateTopologyLayoutLabel();
  syncSettingsInputsFromState();
  setSettingsTab("display");
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
