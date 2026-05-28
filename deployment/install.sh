#!/bin/bash
set -e

# ============================================================
# CEM Backend — Fresh Install Script (Ubuntu 20.04 / 22.04)
# Repository: https://github.com/dadad132/crm-backend-V2
# ============================================================

echo "============================================================"
echo "  CEM Backend Installation Script"
echo "============================================================"
echo ""

# ── Root check ───────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash install.sh)"
   exit 1
fi

# ── Configuration ────────────────────────────────────────────
REPO_URL="https://github.com/dadad132/crm-backend-V2.git"
INSTALL_DIR="/opt/crm-backend"
APP_USER="crm"
APP_GROUP="crm"
PYTHON_BIN="python3.12"
SERVICE_NAME="crm-backend"

echo "📋 Configuration:"
echo "   Repo     : $REPO_URL"
echo "   Directory: $INSTALL_DIR"
echo "   User     : $APP_USER"
echo "   Python   : $PYTHON_BIN"
echo ""

# ── Step 1: System packages ──────────────────────────────────
echo "━━━ Step 1 / 10 — Updating system packages ━━━"
apt-get update -qq
apt-get upgrade -y -qq

# ── Step 2: Python 3.12 (deadsnakes PPA) ─────────────────────
echo "━━━ Step 2 / 10 — Installing Python 3.12 ━━━"
apt-get install -y -qq software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -qq
apt-get install -y -qq \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    sqlite3 \
    git \
    curl \
    ufw \
    rsync

# Verify Python
$PYTHON_BIN --version
echo "✅ Python 3.12 installed"

# ── Step 3: Application user ─────────────────────────────────
echo "━━━ Step 3 / 10 — Creating application user ━━━"
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home-dir "$INSTALL_DIR" --create-home "$APP_USER"
    echo "✅ User '$APP_USER' created"
else
    echo "✅ User '$APP_USER' already exists"
fi

# ── Step 4: Clone / update repository ────────────────────────
echo "━━━ Step 4 / 10 — Cloning repository ━━━"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "   Repository already exists — pulling latest code..."
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
    echo "✅ Repository updated"
else
    # Fresh clone — preserve data.db and app/uploads if they exist from a migration
    if [ -f "/tmp/crm-migrate/data.db" ]; then
        echo "   Found migration data — will restore after clone"
        RESTORE_DATA=true
    fi
    git clone "$REPO_URL" "$INSTALL_DIR"
    echo "✅ Repository cloned"
fi

cd "$INSTALL_DIR"

# ── Step 5: Directory structure ───────────────────────────────
echo "━━━ Step 5 / 10 — Creating directory structure ━━━"
mkdir -p "$INSTALL_DIR/backups"
mkdir -p "$INSTALL_DIR/app/uploads/tickets"
mkdir -p "$INSTALL_DIR/app/uploads/comments"
mkdir -p "$INSTALL_DIR/app/uploads/branding"
mkdir -p "$INSTALL_DIR/app/uploads/profile_pictures"
mkdir -p "$INSTALL_DIR/logs"
echo "✅ Directories created"

# ── Step 6: Python virtual environment ───────────────────────
echo "━━━ Step 6 / 10 — Setting up Python environment ━━━"
$PYTHON_BIN -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

pip install --upgrade pip -q
pip install -r "$INSTALL_DIR/requirements.txt" -q

echo "✅ Python environment ready (all packages installed including reportlab)"

# ── Step 7: .env file ─────────────────────────────────────────
echo "━━━ Step 7 / 10 — Creating .env file ━━━"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    # Auto-generate a secure SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|SECRET_KEY=change-me-in-production|SECRET_KEY=$SECRET_KEY|g" "$INSTALL_DIR/.env"

    echo "✅ .env created with auto-generated SECRET_KEY"
    echo ""
    echo "   ⚠️  Edit $INSTALL_DIR/.env to set your SMTP settings if you want email."
    echo ""
else
    echo "✅ .env already exists — skipping (settings preserved)"
fi

# ── Step 8: Restore migrated data (optional) ─────────────────
echo "━━━ Step 8 / 10 — Data restore ━━━"
if [ -d "/tmp/crm-migrate" ]; then
    echo "   Found /tmp/crm-migrate — restoring data..."

    if [ -f "/tmp/crm-migrate/data.db" ]; then
        cp "/tmp/crm-migrate/data.db" "$INSTALL_DIR/data.db"
        echo "   ✅ data.db restored"
    fi

    if [ -d "/tmp/crm-migrate/uploads" ]; then
        rsync -a "/tmp/crm-migrate/uploads/" "$INSTALL_DIR/app/uploads/"
        echo "   ✅ uploads restored"
    fi

    echo "✅ Migration data restored"
else
    echo "   No migration data found — starting fresh"
    echo "   (To migrate from old server, see instructions at the end)"
fi

# ── Step 9: Permissions ───────────────────────────────────────
echo "━━━ Step 9 / 10 — Setting permissions ━━━"
chown -R "$APP_USER:$APP_GROUP" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod -R 770 "$INSTALL_DIR/backups"
chmod -R 770 "$INSTALL_DIR/app/uploads"
chmod -R 770 "$INSTALL_DIR/logs"
# .env must be readable only by the app user
chmod 640 "$INSTALL_DIR/.env"
echo "✅ Permissions set"

# ── Step 10: Systemd service + firewall + management scripts ──
echo "━━━ Step 10 / 10 — System service & firewall ━━━"

# Write the service file
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=CEM Backend Application
After=network.target
Documentation=$REPO_URL

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$INSTALL_DIR/.env

ExecStart=$INSTALL_DIR/venv/bin/python start_server.py

TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

Restart=on-failure
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR/data.db $INSTALL_DIR/backups $INSTALL_DIR/app/uploads $INSTALL_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
echo "✅ Systemd service installed and enabled"

# Firewall
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8000/tcp  # Application
echo "✅ Firewall configured (ports 22, 80, 443, 8000)"

# Management shortcuts
cat > /usr/local/bin/crm-start <<'SCRIPT'
#!/bin/bash
echo "🚀 Starting CEM Backend..."
systemctl start crm-backend
sleep 2
systemctl status crm-backend --no-pager
SCRIPT

cat > /usr/local/bin/crm-stop <<'SCRIPT'
#!/bin/bash
echo "🛑 Stopping CEM Backend..."
systemctl stop crm-backend
echo "✅ Stopped"
SCRIPT

cat > /usr/local/bin/crm-restart <<'SCRIPT'
#!/bin/bash
echo "🔄 Restarting CEM Backend..."
systemctl restart crm-backend
sleep 2
systemctl status crm-backend --no-pager
SCRIPT

cat > /usr/local/bin/crm-status <<'SCRIPT'
#!/bin/bash
systemctl status crm-backend --no-pager
echo ""
echo "Last 30 log lines:"
journalctl -u crm-backend -n 30 --no-pager
SCRIPT

cat > /usr/local/bin/crm-logs <<'SCRIPT'
#!/bin/bash
journalctl -u crm-backend -f
SCRIPT

cat > /usr/local/bin/crm-update <<'SCRIPT'
#!/bin/bash
echo "⬇️  Pulling latest code from GitHub..."
cd /opt/crm-backend
git fetch origin
git reset --hard origin/main
echo "📦 Updating Python packages..."
source venv/bin/activate
pip install -r requirements.txt -q
echo "🔄 Restarting service..."
systemctl restart crm-backend
sleep 2
systemctl status crm-backend --no-pager
echo "✅ Update complete"
SCRIPT

chmod +x /usr/local/bin/crm-start
chmod +x /usr/local/bin/crm-stop
chmod +x /usr/local/bin/crm-restart
chmod +x /usr/local/bin/crm-status
chmod +x /usr/local/bin/crm-logs
chmod +x /usr/local/bin/crm-update

echo "✅ Management commands installed"

# ── Start the service ─────────────────────────────────────────
echo ""
echo "🚀 Starting the application..."
systemctl start "$SERVICE_NAME"
sleep 3
systemctl status "$SERVICE_NAME" --no-pager || true

# ── Done ──────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo "  ✅ Installation Complete!"
echo "============================================================"
echo ""
echo "  🌐 Access URL : http://$SERVER_IP:8000"
echo "  📁 App folder : $INSTALL_DIR"
echo "  📄 Config file: $INSTALL_DIR/.env"
echo ""
echo "  Management commands:"
echo "    crm-start    — start the app"
echo "    crm-stop     — stop the app"
echo "    crm-restart  — restart the app"
echo "    crm-status   — view status + last 30 log lines"
echo "    crm-logs     — live log stream (Ctrl+C to exit)"
echo "    crm-update   — pull latest code from GitHub and restart"
echo ""
echo "============================================================"
echo "  Migrating from old server?"
echo "============================================================"
echo ""
echo "  On the OLD server, run:"
echo "    mkdir /tmp/crm-migrate"
echo "    cp /path/to/old/data.db /tmp/crm-migrate/"
echo "    cp -r /path/to/old/app/uploads /tmp/crm-migrate/"
echo "    scp -r /tmp/crm-migrate root@<this-server-ip>:/tmp/"
echo ""
echo "  Then re-run this script — it will detect /tmp/crm-migrate"
echo "  and restore your database and uploaded files automatically."
echo ""
echo "============================================================"
