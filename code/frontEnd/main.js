const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const fsp = require("fs/promises");
const readline = require("readline");
const { spawn } = require("child_process");

const CODE_ROOT = path.resolve(__dirname, "..");
const RUNTIME_DIR = path.join(CODE_ROOT, "runtime");
const READY_FLAG_PATH = path.join(RUNTIME_DIR, "backend_ready.flag");
const SHUTDOWN_FLAG_PATH = path.join(RUNTIME_DIR, "shutdown.flag");
const BRIDGE_SCRIPT_PATH = path.join(__dirname, "supervisor_bridge.py");

let launchWindow = null;
let mainWindow = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fileExists(filePath) {
  try {
    await fsp.access(filePath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function clearFile(filePath) {
  try {
    await fsp.unlink(filePath);
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }
}

async function waitForFile(filePath, timeoutMs = 120000, pollMs = 250) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await fileExists(filePath)) {
      return;
    }
    await sleep(pollMs);
  }
  throw new Error(`Timed out waiting for file: ${filePath}`);
}

function buildPythonCandidates() {
  const candidates = [];

  if (process.env.NETTOWER_PYTHON) {
    candidates.push(process.env.NETTOWER_PYTHON);
  }

  const venvPath = path.join(CODE_ROOT, "venv");
  if (process.platform === "win32") {
    candidates.push(path.join(venvPath, "Scripts", "python.exe"));
    candidates.push("py");
    candidates.push("python");
  } else {
    candidates.push(path.join(venvPath, "bin", "python"));
    candidates.push(path.join(venvPath, "bin", "python3"));
    candidates.push("python3");
    candidates.push("python");
  }

  return [...new Set(candidates)];
}

function normalizeSessionConfig(raw = {}) {
  const toInt = (value, fallback) => {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const interfaceValue = typeof raw.interface === "string" ? raw.interface.trim() : "";
  const cidrValue = typeof raw.discovery_target_cidr === "string"
    ? raw.discovery_target_cidr.trim()
    : "";

  return {
    interface: interfaceValue || null,
    discovery_target_cidr: cidrValue || null,
    enable_passive_listener: Boolean(raw.enable_passive_listener),
    enable_active_discovery: Boolean(raw.enable_active_discovery),
    discovery_interval_seconds: Math.max(1, toInt(raw.discovery_interval_seconds, 120)),
    targeted_scan_cooldown_seconds: Math.max(
      0,
      toInt(raw.targeted_scan_cooldown_seconds, 300),
    ),
  };
}

class SupervisorBridge {
  constructor() {
    this.proc = null;
    this.readline = null;
    this.pending = new Map();
    this.nextId = 1;
    this.running = false;
    this.starting = false;
    this.stderrLines = [];
  }

  async ensureProcess() {
    if (this.proc && this.proc.exitCode === null && !this.proc.killed) {
      return;
    }

    let lastError = null;
    const candidates = buildPythonCandidates();

    for (const candidate of candidates) {
      const looksAbsolute = candidate.includes(path.sep);
      if (looksAbsolute && !fs.existsSync(candidate)) {
        continue;
      }

      try {
        await this.spawnProcess(candidate);
        return;
      } catch (error) {
        lastError = error;
      }
    }

    throw new Error(
      `Unable to launch Python bridge. Last error: ${lastError ? lastError.message : "unknown"}`,
    );
  }

  spawnProcess(candidate) {
    return new Promise((resolve, reject) => {
      const args = [];
      if (process.platform === "win32" && candidate === "py") {
        args.push("-3");
      }
      args.push(BRIDGE_SCRIPT_PATH);

      const child = spawn(candidate, args, {
        cwd: CODE_ROOT,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let settled = false;
      const timeout = setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        child.kill();
        reject(new Error(`Timed out launching bridge with: ${candidate}`));
      }, 2500);

      const handleSpawn = () => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        child.removeListener("error", handleError);
        this.attachProcess(child);
        resolve();
      };

      const handleError = (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        child.removeListener("spawn", handleSpawn);
        reject(error);
      };

      child.once("spawn", handleSpawn);
      child.once("error", handleError);
    });
  }

  attachProcess(child) {
    this.proc = child;

    this.readline = readline.createInterface({
      input: child.stdout,
      crlfDelay: Infinity,
    });

    this.readline.on("line", (line) => this.onStdoutLine(line));

    child.stderr.on("data", (chunk) => {
      const text = String(chunk).trim();
      if (text) {
        this.captureStderr(text);
        console.error(`[NetTower bridge] ${text}`);
      }
    });

    child.on("exit", (code, signal) => {
      const stderrTail = this.stderrLines.slice(-20).join("\n");
      const exitMessage = stderrTail
        ? `Python bridge exited (code=${code}, signal=${signal || "none"})\nBridge stderr:\n${stderrTail}`
        : `Python bridge exited (code=${code}, signal=${signal || "none"})`;
      this.failAllPending(
        new Error(exitMessage),
      );
      this.running = false;
      this.starting = false;
      this.proc = null;
      if (this.readline) {
        this.readline.close();
        this.readline = null;
      }
    });
  }

  captureStderr(text) {
    const lines = text.split(/\r?\n/).filter(Boolean);
    this.stderrLines.push(...lines);
    if (this.stderrLines.length > 250) {
      this.stderrLines = this.stderrLines.slice(-250);
    }
  }

  onStdoutLine(line) {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }

    let message;
    try {
      message = JSON.parse(trimmed);
    } catch {
      console.warn(`[NetTower bridge] Non-JSON stdout: ${trimmed}`);
      return;
    }

    if (typeof message.id !== "number") {
      return;
    }

    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }

    clearTimeout(pending.timeout);
    this.pending.delete(message.id);

    if (message.ok) {
      pending.resolve(message.result || {});
      return;
    }

    pending.reject(new Error(message.error || "Bridge command failed"));
  }

  failAllPending(error) {
    for (const [, pending] of this.pending.entries()) {
      clearTimeout(pending.timeout);
      pending.reject(error);
    }
    this.pending.clear();
  }

  async sendCommand(command, payload = {}, timeoutMs = 120000) {
    await this.ensureProcess();
    if (!this.proc || this.proc.exitCode !== null) {
      throw new Error("Bridge process is not available");
    }

    const id = this.nextId++;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for bridge command: ${command}`));
      }, timeoutMs);

      this.pending.set(id, {
        resolve,
        reject,
        timeout,
      });

      const envelope = {
        id,
        command,
        payload,
      };

      this.proc.stdin.write(`${JSON.stringify(envelope)}\n`, (error) => {
        if (!error) {
          return;
        }

        clearTimeout(timeout);
        this.pending.delete(id);
        reject(error);
      });
    });
  }

  async startSession(sessionConfig) {
    if (this.starting) {
      throw new Error("Session startup already in progress");
    }
    if (this.running) {
      return;
    }

    this.starting = true;
    try {
      await fsp.mkdir(RUNTIME_DIR, { recursive: true });
      await clearFile(READY_FLAG_PATH);
      await clearFile(SHUTDOWN_FLAG_PATH);

      await this.sendCommand("start_session", {
        session_config: sessionConfig,
      });

      // Frontend waits for backend readiness by watching for the ready flag.
      await waitForFile(READY_FLAG_PATH);
      this.running = true;
    } catch (error) {
      this.running = false;
      try {
        await this.sendCommand("stop_session", {}, 20000);
      } catch {
        // Best-effort cleanup.
      }
      await clearFile(READY_FLAG_PATH);
      await clearFile(SHUTDOWN_FLAG_PATH);
      throw error;
    } finally {
      this.starting = false;
    }
  }

  async stopSession() {
    if (!this.proc) {
      this.running = false;
      await clearFile(READY_FLAG_PATH);
      await clearFile(SHUTDOWN_FLAG_PATH);
      return;
    }

    try {
      await this.sendCommand("stop_session", {}, 20000);
    } finally {
      this.running = false;
      await clearFile(READY_FLAG_PATH);
      await clearFile(SHUTDOWN_FLAG_PATH);
    }
  }

  async status() {
    const ready = await fileExists(READY_FLAG_PATH);
    return {
      running: this.running,
      starting: this.starting,
      ready,
    };
  }

  async getTopologySnapshot(options = {}) {
    if (!this.proc) {
      return {
        hosts: [],
        edges: [],
        warning: "Session is not running.",
        captured_at: new Date().toISOString(),
        running: false,
      };
    }

    const payload = {
      limit_hosts: options.limitHosts || 250,
      limit_edges: options.limitEdges || 500,
    };
    return this.sendCommand("get_topology_snapshot", payload, 6000);
  }

  async shutdown() {
    try {
      await this.stopSession();
    } catch {
      this.running = false;
    }

    if (!this.proc) {
      return;
    }

    try {
      await this.sendCommand("shutdown", {}, 5000);
    } catch {
      // Process may already be gone.
    }

    if (this.proc && this.proc.exitCode === null) {
      this.proc.kill();
    }

    this.proc = null;
    if (this.readline) {
      this.readline.close();
      this.readline = null;
    }
  }
}

const supervisorBridge = new SupervisorBridge();

function createLaunchWindow() {
  if (launchWindow && !launchWindow.isDestroyed()) {
    launchWindow.focus();
    return;
  }

  launchWindow = new BrowserWindow({
    width: 560,
    height: 700,
    resizable: false,
    title: "NetTower",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  launchWindow.removeMenu();
  launchWindow.loadFile(path.join(__dirname, "windows", "launch.html"));
  launchWindow.on("closed", () => {
    launchWindow = null;
  });
}

function createMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.focus();
    return;
  }

  mainWindow = new BrowserWindow({
    width: 900,
    height: 620,
    minWidth: 760,
    minHeight: 520,
    title: "NetTower Session",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.removeMenu();
  mainWindow.loadFile(path.join(__dirname, "windows", "main.html"));
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function showMainWindow() {
  createMainWindow();

  if (launchWindow && !launchWindow.isDestroyed()) {
    launchWindow.close();
  }
}

function showLaunchWindow() {
  createLaunchWindow();

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.close();
  }
}

ipcMain.handle("runtime:start-session", async (_event, rawSessionConfig) => {
  const sessionConfig = normalizeSessionConfig(rawSessionConfig);
  await supervisorBridge.startSession(sessionConfig);
  showMainWindow();
  return { ok: true };
});

ipcMain.handle("runtime:stop-session", async () => {
  await supervisorBridge.stopSession();
  showLaunchWindow();
  return { ok: true };
});

ipcMain.handle("runtime:get-status", async () => {
  return supervisorBridge.status();
});

ipcMain.handle("runtime:get-topology", async (_event, options) => {
  return supervisorBridge.getTopologySnapshot(options || {});
});

app.whenReady().then(() => {
  createLaunchWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length > 0) {
      return;
    }

    const state = await supervisorBridge.status();
    if (state.running || state.ready) {
      createMainWindow();
      return;
    }

    createLaunchWindow();
  });
});

let quitting = false;
app.on("before-quit", (event) => {
  if (quitting) {
    return;
  }

  event.preventDefault();
  quitting = true;
  supervisorBridge.shutdown().finally(() => {
    app.quit();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
