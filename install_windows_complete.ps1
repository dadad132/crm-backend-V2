# CRM Backend - Complete Windows Installer with Python Auto-Install
# This script will install Python if not found, then install the CRM Backend

$ErrorActionPreference = "Continue"

# Get the directory where this script is located
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR
Write-Host "[i] Running from: $SCRIPT_DIR" -ForegroundColor Cyan
Write-Host ""

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "   CRM Backend - Complete Installer" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    Write-Host "[i] Running with Administrator privileges" -ForegroundColor Cyan
} else {
    Write-Host "[i] Running as regular user" -ForegroundColor Cyan
}
Write-Host ""

# Check if Python is installed
Write-Host "[i] Checking Python installation..." -ForegroundColor Cyan
$pythonInstalled = $false

try {
    $pythonVersion = python --version 2>&1
    $pythonInstalled = $true
    Write-Host "[V] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[X] Python not found!" -ForegroundColor Red
}

if (-not $pythonInstalled) {
    Write-Host ""
    
    if (-not $isAdmin) {
        Write-Host "[!] Python installation requires Administrator privileges" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please either:" -ForegroundColor Yellow
        Write-Host "1. Right-click this file and select 'Run as administrator'" -ForegroundColor Yellow
        Write-Host "2. Or install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host ""
        pause
        exit 1
    }
    
    Write-Host "[i] Downloading Python 3.11.9 installer..." -ForegroundColor Cyan
    Write-Host "[i] Please wait, this may take a few minutes..." -ForegroundColor Cyan
    
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pythonInstaller = "$env:TEMP\python_installer.exe"
    
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller -UseBasicParsing
        Write-Host "[V] Python installer downloaded" -ForegroundColor Green
    } catch {
        Write-Host "[X] Failed to download Python installer" -ForegroundColor Red
        Write-Host "Error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        pause
        exit 1
    }
    
    Write-Host ""
    Write-Host "[i] Installing Python 3.11.9..." -ForegroundColor Cyan
    Write-Host "[i] This will take a few minutes. Please wait..." -ForegroundColor Cyan
    
    # Install Python silently with pip and add to PATH
    $installArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0"
    $process = Start-Process -FilePath $pythonInstaller -ArgumentList $installArgs -Wait -PassThru
    
    if ($process.ExitCode -ne 0) {
        Write-Host "[X] Python installation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        Remove-Item $pythonInstaller -ErrorAction SilentlyContinue
        pause
        exit 1
    }
    
    Write-Host "[V] Python installed successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Clean up installer
    Remove-Item $pythonInstaller -ErrorAction SilentlyContinue
    
    # Refresh environment variables
    Write-Host "[i] Refreshing environment..." -ForegroundColor Cyan
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Host "[V] Python installation complete" -ForegroundColor Green
    Write-Host ""
    
    # Verify Python is now available
    try {
        $pythonVersion = python --version 2>&1
        Write-Host "[V] Python verified: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "[!] Python installed but not found in PATH" -ForegroundColor Yellow
        Write-Host "[!] Please restart this computer and run the installer again" -ForegroundColor Yellow
        pause
        exit 1
    }
}

Write-Host ""

# Check if Git is installed (optional)
try {
    $gitVersion = git --version 2>&1
    Write-Host "[V] Git found: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[!] Git not found - Updates will need to be done manually" -ForegroundColor Yellow
}
Write-Host ""

# Proceed with CRM Backend installation
Write-Host "[i] Starting CRM Backend installation..." -ForegroundColor Cyan
Write-Host ""

# Check if we're in the correct directory
if (-not (Test-Path "app")) {
    Write-Host "[X] Error: Installation files not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "[!] Please make sure you are running this script from the extracted installer folder" -ForegroundColor Yellow
    Write-Host "[!] The folder should contain: app/, requirements.txt, start_server.py, etc." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Current directory: $PWD" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

$AppDir = "$env:USERPROFILE\crm-backend"

if (Test-Path $AppDir) {
    Write-Host "[!] Application directory already exists at $AppDir" -ForegroundColor Yellow
    $reinstall = Read-Host "Remove and reinstall? (y/N)"
    if ($reinstall -eq "y" -or $reinstall -eq "Y") {
        Write-Host "[i] Removing existing installation..." -ForegroundColor Cyan
        Remove-Item -Path $AppDir -Recurse -Force
        Write-Host "[V] Existing installation removed" -ForegroundColor Green
    } else {
        Write-Host "[X] Installation cancelled" -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host "[i] Creating application directory: $AppDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $AppDir -Force | Out-Null

Write-Host "[i] Copying application files..." -ForegroundColor Cyan
if (Test-Path "app")        { Copy-Item -Path "app"        -Destination "$AppDir\app"        -Recurse -Force }
if (Test-Path "alembic")    { Copy-Item -Path "alembic"    -Destination "$AppDir\alembic"    -Recurse -Force }
if (Test-Path "migrations") { Copy-Item -Path "migrations" -Destination "$AppDir\migrations" -Recurse -Force }

$filesToCopy = @("requirements.txt", "alembic.ini", ".env.example", "start_server.py", "auto_update.bat", "README.md")
foreach ($file in $filesToCopy) {
    if (Test-Path $file) { Copy-Item -Path $file -Destination "$AppDir\" -Force }
}
Write-Host "[V] Files copied successfully" -ForegroundColor Green
Write-Host ""

Set-Location $AppDir
Write-Host "[V] Changed to directory: $PWD" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path "requirements.txt")) {
    Write-Host "[X] requirements.txt not found!" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[i] Creating Python virtual environment..." -ForegroundColor Cyan
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to create virtual environment" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "[V] Virtual environment created" -ForegroundColor Green
Write-Host ""

Write-Host "[i] Activating virtual environment..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"
Write-Host "[V] Virtual environment activated" -ForegroundColor Green
Write-Host ""

Write-Host "[i] Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
Write-Host "[V] Pip upgraded" -ForegroundColor Green
Write-Host ""

Write-Host "[i] Installing Python dependencies (this may take a few minutes)..." -ForegroundColor Cyan
Write-Host "[i] Please wait..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install Python dependencies" -ForegroundColor Red
    Write-Host "[!] Try running: pip install -r requirements.txt" -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host "[V] Python dependencies installed successfully!" -ForegroundColor Green
Write-Host ""

Write-Host "[i] Creating necessary directories..." -ForegroundColor Cyan
@("logs", "backups", "updates", "app\uploads\comments", "app\uploads\chat_messages", "app\uploads\tickets", "app\static") | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}
Write-Host "[V] Directories created" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host "[i] Creating .env configuration file..." -ForegroundColor Cyan
    @"
# CRM Backend Configuration
DATABASE_URL=sqlite+aiosqlite:///./data.db
SECRET_KEY=change-this-to-a-random-secret-key-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Update System Configuration
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_URL=https://api.github.com/repos/yourusername/crm-backend/releases/latest
UPDATE_CHECK_INTERVAL=86400
"@ | Out-File -FilePath ".env" -Encoding ASCII
    Write-Host "[V] .env file created" -ForegroundColor Green
} else {
    Write-Host "[i] .env file already exists" -ForegroundColor Cyan
}
Write-Host ""

Write-Host "[i] Initializing database..." -ForegroundColor Cyan
try {
    python -c "import asyncio; import sys; sys.path.insert(0, '.'); from app.core.database import init_models; asyncio.run(init_models()); print('Database initialized successfully')" 2>$null
    Write-Host "[V] Database initialized" -ForegroundColor Green
} catch {
    Write-Host "[!] Database may already be initialized" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[i] Creating desktop shortcut..." -ForegroundColor Cyan
$shortcutPath = "$env:USERPROFILE\Desktop\Start CRM Backend.bat"
@"
@echo off
cd /d "$AppDir"
call .venv\Scripts\activate.bat
python start_server.py
pause
"@ | Out-File -FilePath $shortcutPath -Encoding ASCII
Write-Host "[V] Desktop shortcut created" -ForegroundColor Green
Write-Host ""

$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "   Installation Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "[*] Access URLs:" -ForegroundColor Blue
Write-Host "    Local:    http://localhost:8000" -ForegroundColor Cyan
Write-Host "    Network:  http://${localIP}:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] Application Directory:" -ForegroundColor Blue
Write-Host "    Location: $AppDir" -ForegroundColor Cyan
Write-Host "    Config:   $AppDir\.env" -ForegroundColor Cyan
Write-Host "    Database: $AppDir\data.db" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] How to Start the Server:" -ForegroundColor Blue
Write-Host "    1. Double-click 'Start CRM Backend' on your desktop" -ForegroundColor Cyan
Write-Host "    2. Or run: python start_server.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "[V] Installation complete! You can now start the CRM backend." -ForegroundColor Green
Write-Host ""
pause
