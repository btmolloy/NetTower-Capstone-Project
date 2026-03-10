$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$PythonBin = Join-Path $RootDir "venv\Scripts\python.exe"

if (-not (Test-Path $PythonBin)) {
    Write-Host "Python virtual environment not found at: $PythonBin"
    exit 1
}

if (-not $env:NETTOWER_DISCOVERY_INTERVAL) { $env:NETTOWER_DISCOVERY_INTERVAL = "15" }
if (-not $env:NETTOWER_MONGO_DB_NAME) { $env:NETTOWER_MONGO_DB_NAME = "nettower" }
if (-not $env:NETTOWER_MONGO_AUTO_START) { $env:NETTOWER_MONGO_AUTO_START = "true" }
if (-not $env:NETTOWER_MONGO_HOST) { $env:NETTOWER_MONGO_HOST = "127.0.0.1" }
if (-not $env:NETTOWER_MONGO_PORT) { $env:NETTOWER_MONGO_PORT = "27017" }
if (-not $env:NETTOWER_MONGO_DATA_DIR) { $env:NETTOWER_MONGO_DATA_DIR = "runtime\mongo_data" }
if (-not $env:NETTOWER_MONGO_LOG_PATH) { $env:NETTOWER_MONGO_LOG_PATH = "runtime\mongod.log" }
if (-not $env:NETTOWER_MONGO_RESET_ON_LAUNCH) { $env:NETTOWER_MONGO_RESET_ON_LAUNCH = "true" }
if (-not $env:NETTOWER_MONGO_DELETE_ON_SHUTDOWN) { $env:NETTOWER_MONGO_DELETE_ON_SHUTDOWN = "true" }
if (-not $env:NETTOWER_MONGO_STARTUP_TIMEOUT_SECONDS) { $env:NETTOWER_MONGO_STARTUP_TIMEOUT_SECONDS = "20" }

if (-not $env:NETTOWER_MONGO_URI) {
    $env:NETTOWER_MONGO_URI = "mongodb://$($env:NETTOWER_MONGO_HOST):$($env:NETTOWER_MONGO_PORT)"
}

if (-not $env:NETTOWER_ENABLE_PASSIVE_LISTENER) { $env:NETTOWER_ENABLE_PASSIVE_LISTENER = "true" }
if (-not $env:NETTOWER_ENABLE_ACTIVE_DISCOVERY) { $env:NETTOWER_ENABLE_ACTIVE_DISCOVERY = "true" }

# Do NOT set NETTOWER_DISCOVERY_TARGET_CIDR here.
# Let the backend auto-detect the subnet from the resolved interface unless the user explicitly sets it.

$DisplayInterface = if ($env:NETTOWER_INTERFACE) { $env:NETTOWER_INTERFACE } else { "AUTO" }
$DisplayCidr = if ($env:NETTOWER_DISCOVERY_TARGET_CIDR) { $env:NETTOWER_DISCOVERY_TARGET_CIDR } else { "AUTO" }
$DisplayMongoBinary = if ($env:NETTOWER_MONGO_BINARY_PATH) { $env:NETTOWER_MONGO_BINARY_PATH } else { "PATH lookup (mongod)" }

Write-Host "Starting NetTower..."
Write-Host "  Interface:          $DisplayInterface"
Write-Host "  CIDR:               $DisplayCidr"
Write-Host "  Mongo URI:          $($env:NETTOWER_MONGO_URI)"
Write-Host "  Mongo DB:           $($env:NETTOWER_MONGO_DB_NAME)"
Write-Host "  Mongo Auto Start:   $($env:NETTOWER_MONGO_AUTO_START)"
Write-Host "  Mongo Host:         $($env:NETTOWER_MONGO_HOST)"
Write-Host "  Mongo Port:         $($env:NETTOWER_MONGO_PORT)"
Write-Host "  Mongo Data Dir:     $($env:NETTOWER_MONGO_DATA_DIR)"
Write-Host "  Mongo Log Path:     $($env:NETTOWER_MONGO_LOG_PATH)"
Write-Host "  Mongo Reset Launch: $($env:NETTOWER_MONGO_RESET_ON_LAUNCH)"
Write-Host "  Mongo Delete Exit:  $($env:NETTOWER_MONGO_DELETE_ON_SHUTDOWN)"
Write-Host "  Mongo Binary:       $DisplayMongoBinary"

$MongoInstalled = $null -ne (Get-Command mongod -ErrorAction SilentlyContinue)
$MongoShellInstalled = $null -ne (Get-Command mongosh -ErrorAction SilentlyContinue)

if (-not $MongoInstalled -and -not $env:NETTOWER_MONGO_BINARY_PATH) {
    Write-Host "Warning: mongod was not found in PATH and NETTOWER_MONGO_BINARY_PATH is not set." -ForegroundColor Yellow
    Write-Host "         NetTower will fail to start local Mongo until mongod is installed or a binary path is provided." -ForegroundColor Yellow
}

if ($env:NETTOWER_MONGO_BINARY_PATH -and -not (Test-Path $env:NETTOWER_MONGO_BINARY_PATH)) {
    Write-Host "Warning: NETTOWER_MONGO_BINARY_PATH is set but does not exist: $($env:NETTOWER_MONGO_BINARY_PATH)" -ForegroundColor Yellow
}

if (-not $MongoShellInstalled) {
    Write-Host "Warning: mongosh was not found in PATH." -ForegroundColor Yellow
}

& $PythonBin -m backEnd.main @args