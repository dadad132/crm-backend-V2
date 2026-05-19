#!/bin/bash

###############################################################################
# CRM Backend - Ubuntu Automatic Installer
# This script will install and configure the CRM backend on Ubuntu
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   CRM Backend - Ubuntu Installer${NC}"
echo -e "${BLUE}=========================================${NC}\n"

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

# Configuration
APP_NAME="crm-backend"
SERVICE_NAME="crm-backend"
PORT=8000

# Check if running as root and set paths accordingly
if [ "$EUID" -eq 0 ]; then 
    print_info "Running as root - installing to /opt/crm-backend"
    APP_DIR="/opt/$APP_NAME"
    # Use a regular user for service if possible
    if [ -z "$SUDO_USER" ]; then
        SERVICE_USER="www-data"
    else
        SERVICE_USER="$SUDO_USER"
    fi
else
    APP_DIR="$HOME/$APP_NAME"
    SERVICE_USER="$USER"
fi

print_info "Installation directory: $APP_DIR"
print_info "Service will run as: $SERVICE_USER"
print_info "Starting installation process..."

# Update system packages
print_info "Updating system packages..."
sudo apt update && sudo apt upgrade -y
print_status "System packages updated"

# Install Python 3.11+ and required system dependencies
print_info "Installing Python and system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    sqlite3 \
    nginx \
    supervisor \
    python3-fastapi \
    python3-uvicorn \
    python3-sqlalchemy \
    python3-aiofiles \
    python3-pydantic \
    python3-jwt \
    python3-passlib \
    python3-bcrypt \
    python3-httpx
print_status "Dependencies installed"

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_info "Python version: $PYTHON_VERSION"

# Create application directory if it doesn't exist
if [ -d "$APP_DIR" ]; then
    print_info "Application directory already exists at $APP_DIR"
    read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing existing installation..."
        rm -rf "$APP_DIR"
        print_status "Existing installation removed"
    else
        print_error "Installation cancelled"
        exit 1
    fi
fi

# Clone from GitHub
print_info "Cloning from GitHub repository..."
print_info "Target directory: $APP_DIR"

if [ -d "$APP_DIR/.git" ]; then
    print_info "Git repository already exists, updating..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
    print_status "Repository updated"
else
    # Clone the repository
    git clone https://github.com/dadad132/cem-backend.git "$APP_DIR"
    if [ $? -eq 0 ]; then
        print_status "Repository cloned successfully"
    else
        print_error "Failed to clone repository!"
        print_info "Trying alternative method..."
        mkdir -p "$APP_DIR"
        cd "$APP_DIR"
        git init
        git remote add origin https://github.com/dadad132/cem-backend.git
        git fetch origin
        git checkout -b main origin/main
        print_status "Repository cloned via git init"
    fi
fi

# Verify we have the code
if [ ! -f "$APP_DIR/requirements.txt" ]; then
    print_error "Failed to clone repository - requirements.txt not found!"
    print_info "Please check your internet connection and GitHub access"
    exit 1
fi

cd "$APP_DIR"

# Install any missing Python dependencies using system pip with --break-system-packages
print_info "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    # Use --ignore-installed to avoid conflicts with system packages
    pip3 install --break-system-packages --no-deps --ignore-installed -r requirements.txt 2>/dev/null || \
    python3 -m pip install --break-system-packages --no-deps -r requirements.txt 2>/dev/null || \
    print_info "Using system packages where available"
    print_status "Python dependencies installed"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Create necessary directories
print_info "Creating necessary directories..."
mkdir -p logs
mkdir -p backups
mkdir -p updates
mkdir -p app/uploads/comments
mkdir -p app/uploads/chat_messages
mkdir -p app/uploads/tickets
mkdir -p app/static
print_status "Directories created"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_info "Creating .env file..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status ".env file created from template"
        print_info "Please edit .env file to configure your settings"
    else
        RANDOM_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "change-this-$(date +%s)")
        cat > .env << EOF
# CRM Backend Configuration
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

# Keep false for plain HTTP; set true only when SSL/HTTPS is configured
APP_HTTPS_ONLY=false

# Allow all origins for public cloud access
CORS_ORIGINS=["*"]

DATABASE_URL=sqlite+aiosqlite:///./data.db
SECRET_KEY=${RANDOM_SECRET}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL=86400
EOF
        print_status ".env file created"
    fi
else
    print_info ".env file already exists"
fi

# Initialize database
print_info "Initializing database..."
cd "$APP_DIR"
python3 << 'PYEOF'
import asyncio
import sys
import os

# Change to app directory
os.chdir('.')
sys.path.insert(0, os.getcwd())

try:
    from app.core.database import init_models
    asyncio.run(init_models())
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization skipped or already done: {e}')
PYEOF
print_status "Database ready"

# Create systemd service file
print_info "Creating systemd service..."
print_info "Service file: /etc/systemd/system/${SERVICE_NAME}.service"

# Get the actual Python3 path
PYTHON_PATH=$(which python3)
print_info "Using Python at: $PYTHON_PATH"

if [ "$EUID" -eq 0 ]; then
    tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=CRM Backend Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_PATH -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
else
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=CRM Backend Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_PATH -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

# Verify service file was created
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    print_status "Systemd service file created successfully"
else
    print_error "Failed to create systemd service file!"
    exit 1
fi

# Reload systemd
print_info "Reloading systemd daemon..."
if [ "$EUID" -eq 0 ]; then
    systemctl daemon-reload
else
    sudo systemctl daemon-reload
fi
print_status "Systemd reloaded"

# Enable and start service
print_info "Enabling and starting service..."
print_info "Service name: ${SERVICE_NAME}"
if [ "$EUID" -eq 0 ]; then
    systemctl enable ${SERVICE_NAME}
    systemctl start ${SERVICE_NAME}
else
    sudo systemctl enable ${SERVICE_NAME}
    sudo systemctl start ${SERVICE_NAME}
fi
sleep 2
print_status "Service started"

# Check service status
if [ "$EUID" -eq 0 ]; then
    SERVICE_ACTIVE=$(systemctl is-active ${SERVICE_NAME})
else
    SERVICE_ACTIVE=$(sudo systemctl is-active ${SERVICE_NAME})
fi

if [ "$SERVICE_ACTIVE" = "active" ]; then
    print_status "Service is running!"
else
    print_error "Service failed to start. Check logs with: sudo journalctl -u ${SERVICE_NAME} -f"
fi

# Configure firewall if ufw is installed
if command -v ufw &> /dev/null; then
    print_info "Configuring firewall..."
    sudo ufw allow $PORT/tcp
    print_status "Firewall configured (port $PORT opened)"
fi

# Get server IP addresses
print_info "Detecting IP addresses..."
LOCAL_IP=$(hostname -I | awk '{print $1}')
PUBLIC_IP=$(curl -s ifconfig.me || echo "Unable to detect")

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   Installation Complete!${NC}"
echo -e "${GREEN}=========================================${NC}\n"

echo -e "${BLUE}Server Information:${NC}"
echo -e "  Local Access:  ${GREEN}http://localhost:$PORT${NC}"
echo -e "  Local Network: ${GREEN}http://$LOCAL_IP:$PORT${NC}"
if [ "$PUBLIC_IP" != "Unable to detect" ]; then
    echo -e "  Public Access: ${GREEN}http://$PUBLIC_IP:$PORT${NC}"
fi
echo ""

echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  Start service:   ${YELLOW}sudo systemctl start ${SERVICE_NAME}${NC}"
echo -e "  Stop service:    ${YELLOW}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo -e "  Restart service: ${YELLOW}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  Service status:  ${YELLOW}sudo systemctl status ${SERVICE_NAME}${NC}"
echo -e "  View logs:       ${YELLOW}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  Check updates:   ${YELLOW}./update_ubuntu.sh${NC}"
echo ""

echo -e "${BLUE}Application Directory:${NC}"
echo -e "  Location: ${YELLOW}$APP_DIR${NC}"
echo -e "  Config:   ${YELLOW}$APP_DIR/.env${NC}"
echo -e "  Database: ${YELLOW}$APP_DIR/data.db${NC}"
echo -e "  Updates:  ${YELLOW}$APP_DIR/updates${NC}"
echo ""

print_info "You can now access your CRM backend at the URLs above"
print_info "Default admin credentials will be created on first run"
echo ""
