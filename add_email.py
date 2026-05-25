#!/usr/bin/env python3
"""Add (or remove) a Gmail account to accounts.json."""
import json
import imaplib
import sys
from pathlib import Path

ACCOUNTS_FILE = Path("accounts.json")


def load():
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text())
    # Migrate from .env if first time
    from dotenv import load_dotenv
    import os
    load_dotenv()
    addr = os.environ.get("GMAIL_ADDRESS")
    pw   = os.environ.get("GMAIL_APP_PASSWORD")
    if addr and pw:
        print(f"  Migrating existing account ({addr}) into accounts.json...")
        return [{"address": addr, "app_password": pw}]
    return []


def save(accounts):
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))


def test_login(address, app_password):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(address, app_password)
        mail.logout()
        return True
    except Exception as e:
        print(f"  Login failed: {e}")
        return False


accounts = load()

print("\n=== EMAIL ACCOUNTS ===\n")
if accounts:
    for i, a in enumerate(accounts, 1):
        print(f"  [{i}] {a['address']}")
else:
    print("  (none configured yet)")

print("""
  [A] Add a new email account
  [R] Remove an account
  [Q] Quit
""")

choice = input("  Choose: ").strip().upper()

if choice == "A":
    print("""
  To get a Gmail App Password:
  1. Go to myaccount.google.com → Security → 2-Step Verification
  2. Scroll down → App passwords → Create → copy the 16-char code
""")
    address  = input("  Gmail address: ").strip()
    app_pw   = input("  App password:  ").strip().replace(" ", "")

    if any(a["address"] == address for a in accounts):
        print(f"  {address} is already in accounts.json.")
        sys.exit(0)

    print(f"  Testing login for {address}...")
    if not test_login(address, app_pw):
        print("  Could not log in. Check the address and app password.")
        sys.exit(1)

    accounts.append({"address": address, "app_password": app_pw})
    save(accounts)
    print(f"  ✓ {address} added. It will be included in the next sync.")

elif choice == "R":
    if not accounts:
        print("  No accounts to remove.")
        sys.exit(0)
    idx = input("  Enter number to remove: ").strip()
    try:
        removed = accounts.pop(int(idx) - 1)
        save(accounts)
        print(f"  ✓ {removed['address']} removed.")
    except (IndexError, ValueError):
        print("  Invalid choice.")

elif choice == "Q":
    print("  Bye.")
