# CRM Backend - Windows Installer (PowerShell)
# Automatically sets up the CRM backend on Windows

$ErrorActionPreference = "Stop"

# Get the directory where this script is located
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR
Write-Host "[i] Running from: $SCRIPT_DIR" -ForegroundColor Cyan
Write-Host ""

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "   CRM Backend - Windows Installer" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Write-Host "[!] Please do NOT run this script as Administrator" -ForegroundColor Yellow
    Write-Host "Run as your regular user: .\install_windows.ps1"
    pause
    exit 1
}

Write-Host "[i] Starting installation process..." -ForegroundColor Cyan
Write-Host "[i] Current user: $env:USERNAME" -ForegroundColor Cyan
Write-Host "[i] Current directory: $PWD" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the correct directory
if (-not (Test-Path "app")) {
    Write-Host "[X] Error: Installation files not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "[!] Please run this script from the extracted installer folder" -ForegroundColor Yellow
    Write-Host "[!] The folder should contain: app/, requirements.txt, start_server.py, etc." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

# Check if Python is installed
Write-Host "[i] Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[✓] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[✗] Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.8 or higher from:" -ForegroundColor Yellow
    Write-Host "https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host ""

# Check if Git is installed (optional)
try {
    $gitVersion = git --version 2>&1
    Write-Host "[✓] Git found: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[!] Git not found - Updates will need to be done manually" -ForegroundColor Yellow
}
Write-Host ""

# Create application directory
$AppDir = "$env:USERPROFILE\crm-backend"

if (Test-Path $AppDir) {
    Write-Host "[!] Application directory already exists at $AppDir" -ForegroundColor Yellow
    $reinstall = Read-Host "Remove and reinstall? (y/N)"
    if ($reinstall -eq "y" -or $reinstall -eq "Y") {
        Write-Host "[i] Removing existing installation..." -ForegroundColor Cyan
        Remove-Item -Path $AppDir -Recurse -Force
        Write-Host "[✓] Existing installation removed" -ForegroundColor Green
    } else {
        Write-Host "[✗] Installation cancelled" -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host "[i] Creating application directory: $AppDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $AppDir -Force | Out-Null

# Copy files
Write-Host "[i] Copying application files..." -ForegroundColor Cyan
if (Test-Path "app")        { Copy-Item -Path "app"        -Destination "$AppDir\app"        -Recurse -Force }
if (Test-Path "alembic")    { Copy-Item -Path "alembic"    -Destination "$AppDir\alembic"    -Recurse -Force }
if (Test-Path "migrations") { Copy-Item -Path "migrations" -Destination "$AppDir\migrations" -Recurse -Force }

$filesToCopy = @("requirements.txt", "alembic.ini", ".env.example", "start_server.py", "auto_update.bat", "README.md")
foreach ($file in $filesToCopy) {
    if (Test-Path $file) { Copy-Item -Path $file -Destination "$AppDir\" -Force }
}
Write-Host "[✓] Files copied successfully" -ForegroundColor Green
Write-Host ""

Set-Location $AppDir
Write-Host "[✓] Changed to directory: $PWD" -ForegroundColor Green
Write-Host ""

# Check requirements.txt
if (-not (Test-Path "requirements.txt")) {
    Write-Host "[✗] requirements.txt not found!" -ForegroundColor Red
    pause
    exit 1
}

# Create virtual environment
Write-Host "[i] Creating Python virtual environment..." -ForegroundColor Cyan
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "[✗] Failed to create virtual environment" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "[✓] Virtual environment created" -ForegroundColor Green
Write-Host ""

# Activate virtual environment
Write-Host "[i] Activating virtual environment..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"
Write-Host "[✓] Virtual environment activated" -ForegroundColor Green
Write-Host "[i] Python location: $AppDir\.venv\Scripts\python.exe" -ForegroundColor Cyan
Write-Host ""

# Upgrade pip
Write-Host "[i] Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
Write-Host "[✓] Pip upgraded" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "[i] Installing Python dependencies (this may take a few minutes)..." -ForegroundColor Cyan
Write-Host "[i] Please wait..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[✗] Failed to install Python dependencies" -ForegroundColor Red
    Write-Host "[!] Try running: pip install -r requirements.txt" -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host "[✓] Python dependencies installed successfully!" -ForegroundColor Green
Write-Host ""

# Create directories
Write-Host "[i] Creating necessary directories..." -ForegroundColor Cyan
@("logs", "backups", "updates", "app\uploads\comments", "app\uploads\chat_messages", "app\uploads\tickets", "app\static") | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}
Write-Host "[✓] Directories created" -ForegroundColor Green
Write-Host ""

# Create .env file
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
    Write-Host "[✓] .env file created" -ForegroundColor Green
} else {
    Write-Host "[i] .env file already exists" -ForegroundColor Cyan
}
Write-Host ""

# Initialize database
Write-Host "[i] Initializing database..." -ForegroundColor Cyan
try {
    python -c "import asyncio; import sys; sys.path.insert(0, '.'); from app.core.database import init_models; asyncio.run(init_models()); print('Database initialized successfully')" 2>$null
    Write-Host "[✓] Database initialized" -ForegroundColor Green
} catch {
    Write-Host "[!] Database may already be initialized" -ForegroundColor Yellow
}
Write-Host ""

# Create desktop shortcut
Write-Host "[i] Creating desktop shortcut..." -ForegroundColor Cyan
$shortcutPath = "$env:USERPROFILE\Desktop\Start CRM Backend.bat"
@"
@echo off
cd /d "$AppDir"
call .venv\Scripts\activate.bat
python start_server.py
pause
"@ | Out-File -FilePath $shortcutPath -Encoding ASCII
Write-Host "[✓] Desktop shortcut created" -ForegroundColor Green
Write-Host ""

# Get local IP
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
Write-Host "[*] Useful Commands:" -ForegroundColor Blue
Write-Host "    Start server:    python start_server.py" -ForegroundColor Cyan
Write-Host "    Update:          .\auto_update.bat" -ForegroundColor Cyan
Write-Host "    Location:        cd $AppDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "[✓] You can now start the CRM backend!" -ForegroundColor Green
Write-Host ""
pause
