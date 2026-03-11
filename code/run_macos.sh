#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/venv/bin/python"

if [[ ! -f "$PYTHON_BIN" ]]; then
    echo "Python virtual environment not found at: $PYTHON_BIN"
    exit 1
fi

if [[ -z "${NETTOWER_DISCOVERY_INTERVAL:-}" ]]; then export NETTOWER_DISCOVERY_INTERVAL="15"; fi
if [[ -z "${NETTOWER_MONGO_DB_NAME:-}" ]]; then export NETTOWER_MONGO_DB_NAME="nettower"; fi
if [[ -z "${NETTOWER_MONGO_AUTO_START:-}" ]]; then export NETTOWER_MONGO_AUTO_START="true"; fi
if [[ -z "${NETTOWER_MONGO_HOST:-}" ]]; then export NETTOWER_MONGO_HOST="127.0.0.1"; fi
if [[ -z "${NETTOWER_MONGO_PORT:-}" ]]; then export NETTOWER_MONGO_PORT="27017"; fi
if [[ -z "${NETTOWER_MONGO_DATA_DIR:-}" ]]; then export NETTOWER_MONGO_DATA_DIR="runtime/mongo_data"; fi
if [[ -z "${NETTOWER_MONGO_LOG_PATH:-}" ]]; then export NETTOWER_MONGO_LOG_PATH="runtime/mongod.log"; fi
if [[ -z "${NETTOWER_MONGO_RESET_ON_LAUNCH:-}" ]]; then export NETTOWER_MONGO_RESET_ON_LAUNCH="true"; fi
if [[ -z "${NETTOWER_MONGO_DELETE_ON_SHUTDOWN:-}" ]]; then export NETTOWER_MONGO_DELETE_ON_SHUTDOWN="true"; fi
if [[ -z "${NETTOWER_MONGO_STARTUP_TIMEOUT_SECONDS:-}" ]]; then export NETTOWER_MONGO_STARTUP_TIMEOUT_SECONDS="20"; fi

if [[ -z "${NETTOWER_MONGO_URI:-}" ]]; then
    export NETTOWER_MONGO_URI="mongodb://${NETTOWER_MONGO_HOST}:${NETTOWER_MONGO_PORT}"
fi

if [[ -z "${NETTOWER_ENABLE_PASSIVE_LISTENER:-}" ]]; then export NETTOWER_ENABLE_PASSIVE_LISTENER="true"; fi
if [[ -z "${NETTOWER_ENABLE_ACTIVE_DISCOVERY:-}" ]]; then export NETTOWER_ENABLE_ACTIVE_DISCOVERY="true"; fi

# Do NOT set NETTOWER_DISCOVERY_TARGET_CIDR here.
# Let the backend auto-detect the subnet from the resolved interface unless the user explicitly sets it.

DISPLAY_INTERFACE="${NETTOWER_INTERFACE:-AUTO}"
DISPLAY_CIDR="${NETTOWER_DISCOVERY_TARGET_CIDR:-AUTO}"
DISPLAY_MONGO_BINARY="${NETTOWER_MONGO_BINARY_PATH:-PATH lookup (mongod)}"

echo "Starting NetTower..."
echo "  Interface:          $DISPLAY_INTERFACE"
echo "  CIDR:               $DISPLAY_CIDR"
echo "  Mongo URI:          $NETTOWER_MONGO_URI"
echo "  Mongo DB:           $NETTOWER_MONGO_DB_NAME"
echo "  Mongo Auto Start:   $NETTOWER_MONGO_AUTO_START"
echo "  Mongo Host:         $NETTOWER_MONGO_HOST"
echo "  Mongo Port:         $NETTOWER_MONGO_PORT"
echo "  Mongo Data Dir:     $NETTOWER_MONGO_DATA_DIR"
echo "  Mongo Log Path:     $NETTOWER_MONGO_LOG_PATH"
echo "  Mongo Reset Launch: $NETTOWER_MONGO_RESET_ON_LAUNCH"
echo "  Mongo Delete Exit:  $NETTOWER_MONGO_DELETE_ON_SHUTDOWN"
echo "  Mongo Binary:       $DISPLAY_MONGO_BINARY"

MONGO_INSTALLED="false"
MONGO_SHELL_INSTALLED="false"

if command -v mongod >/dev/null 2>&1; then
    MONGO_INSTALLED="true"
fi

if command -v mongosh >/dev/null 2>&1; then
    MONGO_SHELL_INSTALLED="true"
fi

if [[ "$MONGO_INSTALLED" == "false" && -z "${NETTOWER_MONGO_BINARY_PATH:-}" ]]; then
    echo "Warning: mongod was not found in PATH and NETTOWER_MONGO_BINARY_PATH is not set."
    echo "         NetTower will fail to start local Mongo until mongod is installed or a binary path is provided."
fi

if [[ -n "${NETTOWER_MONGO_BINARY_PATH:-}" && ! -f "${NETTOWER_MONGO_BINARY_PATH}" ]]; then
    echo "Warning: NETTOWER_MONGO_BINARY_PATH is set but does not exist: ${NETTOWER_MONGO_BINARY_PATH}"
fi

if [[ "$MONGO_SHELL_INSTALLED" == "false" ]]; then
    echo "Warning: mongosh was not found in PATH."
fi

exec "$PYTHON_BIN" -m backEnd.main "$@"