#!/usr/bin/env python3
"""
Interactive setup wizard — run this once on your VPS.
It walks you through every credential and writes your .env automatically.
"""
import os
import sys
import subprocess
from pathlib import Path

ENV_FILE = Path(".env")

# ── Helpers ───────────────────────────────────────────────────────────────────

def step(n, title):
    print(f"\n{'─'*55}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*55}")

def prompt(label, hint=""):
    if hint:
        print(f"  → {hint}")
    val = input(f"  {label}: ").strip()
    if not val:
        print("  (skipped)")
    return val

def confirm(msg):
    return input(f"\n  {msg} [y/n]: ").strip().lower() == "y"

# ── Step 1: Gmail app password ────────────────────────────────────────────────

step(1, "Gmail App Password")
print("""
  An App Password lets this script read your Gmail without
  using your real password. Steps to get one:

  1. Go to:  myaccount.google.com
  2. Click: Security (left sidebar)
  3. Under "How you sign in" → click: 2-Step Verification
     (You must have 2FA enabled. If not, enable it first.)
  4. Scroll to the bottom → click: App passwords
  5. Name it anything, e.g. "YNAB Sync"
  6. Google shows a 16-character code like: abcd efgh ijkl mnop
     Copy that code — you won't see it again.
""")
input("  Press ENTER when you have your App Password ready...")

gmail_address = prompt("Your Gmail address", "e.g. yourname@gmail.com")
gmail_app_pw = prompt(
    "App Password (spaces are OK)",
    "Paste the 16-char code Google gave you"
)
gmail_app_pw = gmail_app_pw.replace(" ", "")  # strip spaces

# ── Step 2: YNAB token ────────────────────────────────────────────────────────

step(2, "YNAB Personal Access Token")
print("""
  Steps to get your YNAB token:

  1. Go to:  app.youneedabudget.com
  2. Click your name (top-left) → My Account
  3. Scroll down to: Developer Settings
  4. Click: New Token → give it a name → Copy the token
""")
input("  Press ENTER when you have your YNAB token ready...")

ynab_token = prompt("YNAB Token", "Paste your token here")

# ── Step 3: Discover YNAB budget + account ────────────────────────────────────

step(3, "Choose your YNAB Budget and Account")

try:
    import requests
except ImportError:
    print("\n  Installing dependencies first...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    import requests

headers = {"Authorization": f"Bearer {ynab_token}"}

print("\n  Fetching your budgets...")
r = requests.get("https://api.ynab.com/v1/budgets", headers=headers)
if r.status_code != 200:
    print(f"  ERROR: YNAB returned {r.status_code}. Check your token.")
    sys.exit(1)

budgets = r.json()["data"]["budgets"]
print()
for i, b in enumerate(budgets, 1):
    print(f"  [{i}] {b['name']}")

choice = input("\n  Enter the number of your budget: ").strip()
try:
    budget = budgets[int(choice) - 1]
    budget_id = budget["id"]
    print(f"  Selected: {budget['name']}")
except (IndexError, ValueError):
    print("  Invalid choice — exiting.")
    sys.exit(1)

print("\n  Fetching accounts in that budget...")
r = requests.get(f"https://api.ynab.com/v1/budgets/{budget_id}/accounts", headers=headers)
accounts = [a for a in r.json()["data"]["accounts"] if not a["deleted"] and not a["closed"]]

print()
for i, a in enumerate(accounts, 1):
    print(f"  [{i}] {a['name']}  ({a['type']})")

choice = input("\n  Enter the number of the account to post transactions to: ").strip()
try:
    account = accounts[int(choice) - 1]
    account_id = account["id"]
    print(f"  Selected: {account['name']}")
except (IndexError, ValueError):
    print("  Invalid choice — exiting.")
    sys.exit(1)

# ── Step 4: Write .env ────────────────────────────────────────────────────────

step(4, "Saving Configuration")

env_content = f"""GMAIL_ADDRESS={gmail_address}
GMAIL_APP_PASSWORD={gmail_app_pw}
YNAB_TOKEN={ynab_token}
YNAB_BUDGET_ID={budget_id}
YNAB_ACCOUNT_ID={account_id}
"""

ENV_FILE.write_text(env_content)
print(f"\n  .env written successfully.")

# ── Step 5: Test run ───────────────────────────────────────────────────────────

step(5, "Test Run")
print("""
  Everything is configured. You can now:

  • Run manually anytime:    python3 main.py
  • Set up daily auto-run:  bash deploy.sh
  • Check logs:             tail -f sync.log
""")

if confirm("Run a test sync right now? (fetches last 7 days of emails)"):
    print()
    subprocess.run([sys.executable, "main.py"])
else:
    print("\n  Skipped. Run 'python3 main.py' when you're ready.")

print("\n  Setup complete.\n")
