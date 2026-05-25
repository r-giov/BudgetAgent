#!/usr/bin/env python3
"""
Interactive Telegram bot — run as a systemd service on your VPS.
Commands: /sync  /balance  /goal  /budget
"""
import os
import sys
import time
import subprocess
import requests as req
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API     = f"https://api.telegram.org/bot{TOKEN}"
YNAB_BASE = "https://api.ynab.com/v1"

DIR = Path(__file__).parent


# ── Telegram helpers ──────────────────────────────────────────────────────────

def send(text: str):
    req.post(f"{API}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=10)

def get_updates(offset: int):
    r = req.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
    return r.json().get("result", [])


# ── YNAB helpers ──────────────────────────────────────────────────────────────

def ynab_headers():
    return {"Authorization": f"Bearer {os.environ['YNAB_TOKEN']}"}

def budget_id():
    return os.environ["YNAB_BUDGET_ID"]

def account_id():
    return os.environ["YNAB_ACCOUNT_ID"]


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_sync():
    send("⏳ Running email sync...")
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True, text=True, cwd=DIR,
    )
    if result.returncode == 0:
        log_path = DIR / "sync.log"
        lines = log_path.read_text().strip().splitlines() if log_path.exists() else []
        summary = next((l.split("INFO")[-1].strip() for l in reversed(lines) if "Done" in l), "Sync complete.")
        send(f"✅ {summary}")
    else:
        send(f"❌ Sync failed:\n`{result.stderr[-400:]}`")


def cmd_balance():
    r = req.get(f"{YNAB_BASE}/budgets/{budget_id()}/accounts", headers=ynab_headers())
    accounts = r.json()["data"]["accounts"]
    acct = next((a for a in accounts if a["id"] == account_id()), None)
    if acct:
        balance = acct["balance"] / 1000
        send(f"💰 *{acct['name']}*\nBalance: `${balance:,.2f}`")
    else:
        send("Could not find account. Check YNAB_ACCOUNT_ID in .env")


def cmd_goal():
    r = req.get(f"{YNAB_BASE}/budgets/{budget_id()}/categories", headers=ynab_headers())
    travel = None
    for group in r.json()["data"]["category_groups"]:
        for cat in group["categories"]:
            if "travel" in cat["name"].lower() and not cat["deleted"]:
                travel = cat
                break

    if not travel or not travel.get("goal_target"):
        send("No travel goal set yet. Run `python3 create_goal.py` on the VPS.")
        return

    saved  = travel["balance"] / 1000
    target = travel["goal_target"] / 1000
    pct    = min(100.0, (saved / target) * 100) if target > 0 else 0
    filled = int(pct // 10)
    bar    = "█" * filled + "░" * (10 - filled)

    send(
        f"✈️ *Travel Goal*\n"
        f"`{bar}` {pct:.1f}%\n"
        f"Saved: `${saved:,.2f}` / `${target:,.2f}`\n"
        f"Still need: `${max(0, target - saved):,.2f}`"
    )


def cmd_budget():
    r = req.get(
        f"{YNAB_BASE}/budgets/{budget_id()}/months/current",
        headers=ynab_headers()
    )
    m = r.json()["data"]["month"]
    income   = m["income"] / 1000
    budgeted = m["budgeted"] / 1000
    spent    = abs(m["activity"]) / 1000
    leftover = m["to_be_budgeted"] / 1000

    send(
        f"📊 *This Month*\n"
        f"Income:    `${income:,.2f}`\n"
        f"Budgeted:  `${budgeted:,.2f}`\n"
        f"Spent:     `${spent:,.2f}`\n"
        f"Available: `${leftover:,.2f}`"
    )


def cmd_start():
    send(
        "👋 *BudgetAgent is live.*\n\n"
        "/sync — pull new transactions from Gmail → YNAB\n"
        "/balance — check your account balance\n"
        "/goal — travel savings progress\n"
        "/budget — this month's overview"
    )


COMMANDS = {
    "/start":   cmd_start,
    "/sync":    cmd_sync,
    "/balance": cmd_balance,
    "/goal":    cmd_goal,
    "/budget":  cmd_budget,
}


# ── Polling loop ──────────────────────────────────────────────────────────────

def main():
    print("BudgetAgent bot started. Polling for messages...")
    send("🤖 BudgetAgent online. Type /start for commands.")
    offset = 0
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                msg  = update.get("message", {})
                text = msg.get("text", "").strip().split()[0]
                chat = str(msg.get("chat", {}).get("id", ""))
                if chat != CHAT_ID:
                    continue
                handler = COMMANDS.get(text)
                if handler:
                    handler()
                elif text.startswith("/"):
                    send("Unknown command. Try: /sync /balance /goal /budget")
        except KeyboardInterrupt:
            print("Bot stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
