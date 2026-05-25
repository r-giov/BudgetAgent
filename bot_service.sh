#!/bin/bash
# Sets up telegram_bot.py as a systemd service so it runs 24/7 and restarts on reboot.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="/etc/systemd/system/budgetagent-bot.service"

echo "── Creating systemd service ──"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=BudgetAgent Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable budgetagent-bot
systemctl start budgetagent-bot

echo ""
echo "✓ Bot service running. Useful commands:"
echo "  systemctl status budgetagent-bot   ← check it's running"
echo "  journalctl -u budgetagent-bot -f   ← live logs"
echo "  systemctl restart budgetagent-bot  ← restart"
echo "  systemctl stop budgetagent-bot     ← stop"
