const form = document.getElementById("session-config-form");
const startButton = document.getElementById("start-session-btn");
const statusElement = document.getElementById("launch-status");
const loadingElement = document.getElementById("launch-loading");

function setStatus(message, level = "info") {
  statusElement.textContent = message;
  statusElement.classList.remove("status-info", "status-success", "status-error");
  statusElement.classList.add(`status-${level}`);
}

function setLoading(isLoading) {
  const fields = form.querySelectorAll("input, button");
  for (const field of fields) {
    field.disabled = isLoading;
  }
  loadingElement.classList.toggle("is-hidden", !isLoading);
  startButton.textContent = isLoading ? "Starting Session..." : "Start Session";
}

function collectSessionConfig() {
  return {
    interface: document.getElementById("interface").value.trim(),
    discovery_target_cidr: document.getElementById("discovery_target_cidr").value.trim(),
    enable_passive_listener: document.getElementById("enable_passive_listener").checked,
    enable_active_discovery: document.getElementById("enable_active_discovery").checked,
    discovery_interval_seconds: Number.parseInt(
      document.getElementById("discovery_interval_seconds").value,
      10,
    ),
    targeted_scan_cooldown_seconds: Number.parseInt(
      document.getElementById("targeted_scan_cooldown_seconds").value,
      10,
    ),
  };
}

async function initState() {
  try {
    const state = await window.nettower.getStatus();
    if (state.starting) {
      setLoading(true);
      setStatus("Session startup already in progress. Waiting for readiness...", "info");
      return;
    }
    setStatus("Ready to start session.", "info");
  } catch (error) {
    setStatus(`Unable to query runtime status: ${error.message}`, "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const sessionConfig = collectSessionConfig();

  setLoading(true);
  setStatus("Launching Supervisor and waiting for backend readiness...", "info");

  try {
    await window.nettower.startSession(sessionConfig);
    setStatus("Session started.", "success");
  } catch (error) {
    setLoading(false);
    setStatus(`Failed to start session: ${error.message}`, "error");
  }
});

initState();
