const form = document.getElementById("session-config-form");
const startButton = document.getElementById("start-session-btn");
const statusElement = document.getElementById("launch-status");
const loadingElement = document.getElementById("launch-loading");

const interfaceInput = document.getElementById("interface");
const cidrInput = document.getElementById("discovery_target_cidr");
const passiveInput = document.getElementById("enable_passive_listener");
const activeInput = document.getElementById("enable_active_discovery");
const discoveryIntervalInput = document.getElementById("discovery_interval_seconds");
const cooldownInput = document.getElementById("targeted_scan_cooldown_seconds");

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

function isValidIPv4Cidr(value) {
  const trimmed = value.trim();
  const [ipPart, prefixPart] = trimmed.split("/");
  if (!ipPart || !prefixPart) {
    return false;
  }

  const prefix = Number.parseInt(prefixPart, 10);
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) {
    return false;
  }

  const octets = ipPart.split(".");
  if (octets.length !== 4) {
    return false;
  }

  for (const octet of octets) {
    const valueNum = Number.parseInt(octet, 10);
    if (!Number.isInteger(valueNum) || valueNum < 0 || valueNum > 255) {
      return false;
    }
  }

  return true;
}

function collectSessionConfig() {
  return {
    interface: interfaceInput.value.trim(),
    discovery_target_cidr: cidrInput.value.trim(),
    enable_passive_listener: passiveInput.checked,
    enable_active_discovery: activeInput.checked,
    discovery_interval_seconds: Number.parseInt(discoveryIntervalInput.value, 10),
    targeted_scan_cooldown_seconds: Number.parseInt(cooldownInput.value, 10),
  };
}

function validateSessionConfig(config) {
  if (!config.interface) {
    return "Interface is required.";
  }
  if (!/^[A-Za-z0-9._:-]+$/.test(config.interface)) {
    return "Interface contains invalid characters.";
  }
  if (!config.discovery_target_cidr) {
    return "Discovery CIDR is required.";
  }
  if (!isValidIPv4Cidr(config.discovery_target_cidr)) {
    return "Discovery CIDR must be a valid IPv4 CIDR (example: 192.168.1.0/24).";
  }
  if (!Number.isInteger(config.discovery_interval_seconds) || config.discovery_interval_seconds < 1) {
    return "Discovery interval seconds must be an integer greater than 0.";
  }
  if (
    !Number.isInteger(config.targeted_scan_cooldown_seconds)
    || config.targeted_scan_cooldown_seconds < 0
  ) {
    return "Targeted scan cooldown seconds must be a non-negative integer.";
  }
  if (!config.enable_passive_listener && !config.enable_active_discovery) {
    return "Enable at least one discovery mode (passive or active).";
  }
  return null;
}

function configureNativeValidation() {
  const updateInterfaceValidity = () => {
    const value = interfaceInput.value.trim();
    if (!value) {
      interfaceInput.setCustomValidity("Interface is required.");
      return;
    }
    if (!/^[A-Za-z0-9._:-]+$/.test(value)) {
      interfaceInput.setCustomValidity("Use letters, numbers, dots, underscores, dashes, or colons.");
      return;
    }
    interfaceInput.setCustomValidity("");
  };

  const updateCidrValidity = () => {
    const value = cidrInput.value.trim();
    if (!value) {
      cidrInput.setCustomValidity("Discovery CIDR is required.");
      return;
    }
    if (!isValidIPv4Cidr(value)) {
      cidrInput.setCustomValidity("Expected format like 192.168.1.0/24.");
      return;
    }
    cidrInput.setCustomValidity("");
  };

  interfaceInput.addEventListener("input", updateInterfaceValidity);
  cidrInput.addEventListener("input", updateCidrValidity);
  updateInterfaceValidity();
  updateCidrValidity();
}

async function initState() {
  configureNativeValidation();

  try {
    const runtimeState = await window.nettower.getStatus();
    if (runtimeState.starting) {
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

  if (!form.reportValidity()) {
    return;
  }

  const sessionConfig = collectSessionConfig();
  const validationError = validateSessionConfig(sessionConfig);
  if (validationError) {
    setStatus(validationError, "error");
    return;
  }

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
