#!/bin/bash
# Run this on your Hostinger VPS after uploading the project
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "── Setting up Python virtual environment ──"
python3 -m venv "$SCRIPT_DIR/venv"
"$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

echo "── Creating .env ──"
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo ".env created. Fill in your credentials before running main.py."
else
    echo ".env already exists, skipping."
fi

echo "── Registering cron job (daily 7:00 AM) ──"
CRON_LINE="0 7 * * * cd $SCRIPT_DIR && $SCRIPT_DIR/venv/bin/python main.py >> $SCRIPT_DIR/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -v "BudgetAgent"; echo "$CRON_LINE" ) | crontab -

echo ""
echo "Done. Verify with: crontab -l"
echo "To run manually:  $SCRIPT_DIR/venv/bin/python main.py"
echo "To check logs:    tail -f $SCRIPT_DIR/sync.log"
