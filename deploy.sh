#!/bin/bash
# Run this on your Hostinger VPS after uploading the project
set -e

echo "── Installing Python dependencies ──"
python3 -m pip install --user -r requirements.txt

echo "── Creating .env ──"
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env created. Fill in your credentials before running main.py."
else
    echo ".env already exists, skipping."
fi

echo "── Registering cron job (daily 7:00 AM) ──"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_LINE="0 7 * * * cd $SCRIPT_DIR && python3 main.py >> $SCRIPT_DIR/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -v "ynab-email-sync"; echo "$CRON_LINE" ) | crontab -

echo ""
echo "Done. Verify with: crontab -l"
echo "To run manually:  python3 main.py"
echo "To check logs:    tail -f sync.log"
