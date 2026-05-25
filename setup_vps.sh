#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  VPS Setup: MT5 Trading + Dev Environment
#  Ubuntu/Debian — run as root
#  Access GUI after setup: http://YOUR_VPS_IP:6080
# ─────────────────────────────────────────────────────────────────
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[+]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
section() { echo -e "\n${GREEN}══ $1 ══${NC}"; }

# ── 1. System update ──────────────────────────────────────────────
section "System Update"
apt update && apt upgrade -y
apt install -y curl wget git vim htop ufw net-tools python3 python3-pip python3-venv

# ── 2. Swap (4GB — critical for MT5 stability) ───────────────────
section "Swap Space"
if [ ! -f /swapfile ]; then
    info "Creating 4GB swapfile..."
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p
    info "Swap created."
else
    warn "Swapfile already exists, skipping."
fi

# ── 3. Wine (for MT5) ─────────────────────────────────────────────
section "Wine Installation"
dpkg --add-architecture i386
mkdir -pm755 /etc/apt/keyrings
curl -s https://dl.winehq.org/wine-builds/winehq.key | gpg --dearmor -o /etc/apt/keyrings/winehq.gpg
echo "deb [signed-by=/etc/apt/keyrings/winehq.gpg] https://dl.winehq.org/wine-builds/ubuntu/ $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/winehq.list
apt update
apt install -y --install-recommends winehq-stable
apt install -y winetricks
info "Wine $(wine --version) installed."

# ── 4. Virtual display + desktop + browser VNC ───────────────────
section "GUI / Virtual Display (noVNC)"
apt install -y xvfb x11vnc xfce4 xfce4-terminal xfce4-screensaver dbus-x11
apt install -y novnc websockify

# Set a VNC password
VNC_PASS=${VNC_PASSWORD:-"budgetagent123"}
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASS" /root/.vnc/passwd
info "VNC password set to: $VNC_PASS  (change in /root/.vnc/passwd)"

# ── 5. Wine prefix for MT5 (64-bit) ──────────────────────────────
section "Wine Prefix (MT5)"
export WINEPREFIX=/root/.mt5
export WINEARCH=win64
wine wineboot --init 2>/dev/null || true
winetricks -q vcrun2019 msxml6 2>/dev/null || true
info "Wine prefix ready at /root/.mt5"

# ── 6. Download MT5 installer ─────────────────────────────────────
section "MetaTrader 5"
MT5_DIR=/root/mt5
mkdir -p "$MT5_DIR"
if [ ! -f "$MT5_DIR/mt5setup.exe" ]; then
    info "Downloading MT5..."
    wget -q -O "$MT5_DIR/mt5setup.exe" \
        "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
    info "MT5 installer downloaded."
fi
info "Run MT5 setup manually after reboot via the browser GUI (http://YOUR_IP:6080)"
info "Command when in GUI terminal:  WINEPREFIX=/root/.mt5 wine /root/mt5/mt5setup.exe"

# ── 7. Systemd services ───────────────────────────────────────────
section "Systemd Services"

# Xvfb (virtual display :1)
cat > /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=Virtual Display (Xvfb)
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :1 -screen 0 1280x800x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# XFCE desktop
cat > /etc/systemd/system/xfce-desktop.service << 'EOF'
[Unit]
Description=XFCE Desktop
After=xvfb.service
Requires=xvfb.service

[Service]
Environment=DISPLAY=:1
Environment=DBUS_SESSION_BUS_ADDRESS=autolaunch:
ExecStart=/usr/bin/startxfce4
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# x11vnc (VNC server)
cat > /etc/systemd/system/x11vnc.service << 'EOF'
[Unit]
Description=x11vnc VNC Server
After=xfce-desktop.service
Requires=xvfb.service

[Service]
ExecStart=/usr/bin/x11vnc -display :1 -rfbauth /root/.vnc/passwd -rfbport 5900 -forever -shared -noxdamage
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# noVNC (browser access on port 6080)
cat > /etc/systemd/system/novnc.service << 'EOF'
[Unit]
Description=noVNC Browser Gateway
After=x11vnc.service

[Service]
ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# MT5 (autostart after desktop is ready)
cat > /etc/systemd/system/mt5.service << 'EOF'
[Unit]
Description=MetaTrader 5
After=xfce-desktop.service
Requires=xvfb.service

[Service]
Environment=DISPLAY=:1
Environment=WINEPREFIX=/root/.mt5
ExecStart=/usr/bin/wine /root/.mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xvfb xfce-desktop x11vnc novnc
# MT5 enabled separately after installation
info "Services registered. MT5 service will auto-enable after you install it."

# ── 8. code-server (VS Code in browser on port 8080) ─────────────
section "code-server (VS Code)"
curl -fsSL https://code-server.dev/install.sh | sh
cat > /etc/systemd/system/code-server.service << EOF
[Unit]
Description=VS Code Server
After=network.target

[Service]
ExecStart=/usr/bin/code-server --bind-addr 0.0.0.0:8080 --auth password
Environment=PASSWORD=budgetagent123
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl enable code-server
info "code-server will be available at http://YOUR_IP:8080"

# ── 9. Firewall ───────────────────────────────────────────────────
section "Firewall"
ufw allow ssh
ufw allow 6080   # noVNC browser GUI
ufw allow 8080   # code-server VS Code
ufw --force enable
info "Firewall configured."

# ── 10. Start everything ──────────────────────────────────────────
section "Starting Services"
systemctl start xvfb
sleep 2
systemctl start xfce-desktop
sleep 2
systemctl start x11vnc
systemctl start novnc
systemctl start code-server

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  VPS Setup Complete${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""
echo "  Browser Desktop (GUI):  http://$(hostname -I | awk '{print $1}'):6080"
echo "  VS Code in browser:     http://$(hostname -I | awk '{print $1}'):8080"
echo "  Password for both:      budgetagent123"
echo ""
echo "  To install MT5:"
echo "  1. Open the browser GUI above"
echo "  2. Open a terminal in XFCE"
echo "  3. Run: WINEPREFIX=/root/.mt5 wine /root/mt5/mt5setup.exe"
echo "  4. After install: systemctl enable --now mt5"
echo ""
echo -e "${YELLOW}  Change default passwords in /etc/systemd/system/code-server.service${NC}"
echo -e "${YELLOW}  and /root/.vnc/passwd (run: x11vnc -storepasswd)${NC}"
echo ""
