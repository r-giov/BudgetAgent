#!/usr/bin/env python3
"""
Run this once to configure Telegram.
It guides you through creating a bot and finding your Chat ID.
"""
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()
ENV = Path(".env")


def step(n, title):
    print(f"\n{'─'*55}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*55}")


# ── Step 1: Create bot via BotFather ─────────────────────────────────────────

step(1, "Create your Telegram Bot")
print("""
  1. Open Telegram and search for: @BotFather
  2. Send it the message:  /newbot
  3. Follow the prompts — pick any name and username
  4. BotFather will give you a token like:
       1234567890:ABCdefGhIJKlmNoPQRstUVwxYZ
  5. Copy that token.
""")
input("  Press ENTER when you have your bot token...")

token = input("  Paste your bot token: ").strip()

# Verify token works
r = requests.get(f"https://api.telegram.org/bot{token}/getMe")
if r.status_code != 200 or not r.json().get("ok"):
    print(f"\n  ERROR: Token invalid. Got: {r.text}")
    exit(1)

bot_name = r.json()["result"]["first_name"]
bot_username = r.json()["result"]["username"]
print(f"\n  ✓ Bot verified: {bot_name} (@{bot_username})")


# ── Step 2: Get Chat ID ───────────────────────────────────────────────────────

step(2, "Get your Chat ID")
print(f"""
  1. Open Telegram and search for your bot: @{bot_username}
  2. Send it ANY message (e.g. "hello")
  3. Come back here and press ENTER.
""")
input("  Press ENTER after you've messaged your bot...")

# Poll for the message
print("  Fetching your chat ID...")
time.sleep(1)
r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
updates = r.json().get("result", [])

if not updates:
    print("  No messages found. Make sure you sent a message to your bot and try again.")
    exit(1)

chat_id = str(updates[-1]["message"]["chat"]["id"])
print(f"  ✓ Chat ID found: {chat_id}")


# ── Step 3: Save to .env ──────────────────────────────────────────────────────

step(3, "Saving to .env")

set_key(str(ENV), "TELEGRAM_BOT_TOKEN", token)
set_key(str(ENV), "TELEGRAM_CHAT_ID", chat_id)
print("  ✓ TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID saved to .env")


# ── Step 4: Test message ──────────────────────────────────────────────────────

step(4, "Sending test message")

requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
    "chat_id": chat_id,
    "text": "✅ BudgetAgent connected! Your YNAB sync notifications will appear here.",
    "parse_mode": "Markdown",
})
print("  ✓ Test message sent — check your Telegram.\n")
print("  Now start the bot service:")
print("  bash bot_service.sh\n")
