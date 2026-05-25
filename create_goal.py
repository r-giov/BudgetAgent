#!/usr/bin/env python3
"""
Interactive script to set a savings goal on any YNAB category.
Run this once to configure your Travel (or any) savings target.
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.ynab.com/v1"
TOKEN = os.environ.get("YNAB_TOKEN")
BUDGET_ID = os.environ.get("YNAB_BUDGET_ID")

if not TOKEN or not BUDGET_ID:
    print("ERROR: .env not configured. Run setup.py first.")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def get_categories():
    r = requests.get(f"{BASE}/budgets/{BUDGET_ID}/categories", headers=HEADERS)
    r.raise_for_status()
    groups = r.json()["data"]["category_groups"]
    categories = []
    for group in groups:
        if group["hidden"] or group["deleted"]:
            continue
        for cat in group["categories"]:
            if not cat["hidden"] and not cat["deleted"]:
                categories.append({
                    "id": cat["id"],
                    "name": cat["name"],
                    "group": group["name"],
                    "balance": cat["balance"] / 1000,
                    "goal_type": cat.get("goal_type"),
                    "goal_target": (cat.get("goal_target") or 0) / 1000,
                })
    return categories


def set_goal(category_id, goal_type, target_amount, target_month=None):
    payload = {
        "category": {
            "goal_type": goal_type,
            "goal_target": int(target_amount * 1000),
        }
    }
    if target_month:
        payload["category"]["goal_target_month"] = target_month

    r = requests.patch(
        f"{BASE}/budgets/{BUDGET_ID}/categories/{category_id}",
        headers=HEADERS,
        json=payload,
    )
    r.raise_for_status()
    return r.json()["data"]["category"]


# ── List categories ───────────────────────────────────────────────────────────

print("\n=== YOUR YNAB CATEGORIES ===\n")
categories = get_categories()

for i, c in enumerate(categories, 1):
    goal_info = ""
    if c["goal_type"]:
        goal_info = f"  [Goal: ${c['goal_target']:.0f}]"
    print(f"  [{i:>2}] {c['group']} → {c['name']}  (balance: ${c['balance']:.2f}){goal_info}")

print()
print("  Tip: If you don't see a 'Travel' category, create it in the YNAB app")
print("       then re-run this script.")
print()

choice = input("Enter the number of the category to set a goal on: ").strip()
try:
    cat = categories[int(choice) - 1]
except (IndexError, ValueError):
    print("Invalid choice.")
    sys.exit(1)

print(f"\nSelected: {cat['name']}")

# ── Goal type ─────────────────────────────────────────────────────────────────

print("""
Goal type:
  [1] Save a specific amount (no deadline)
  [2] Save a specific amount by a target date
  [3] Add a fixed amount each month
""")

goal_choice = input("Choose [1/2/3]: ").strip()

target_amount = float(input("Target amount ($): ").replace("$", "").strip())

target_month = None
goal_type = "TB"

if goal_choice == "2":
    goal_type = "TBD"
    print("\nTarget date — enter the month you want to reach your goal.")
    year = input("  Year (e.g. 2027): ").strip()
    month = input("  Month number (1-12): ").strip().zfill(2)
    target_month = f"{year}-{month}-01"
elif goal_choice == "3":
    goal_type = "MF"

# ── Apply goal ────────────────────────────────────────────────────────────────

print(f"\nSetting ${target_amount:.2f} goal on '{cat['name']}'...")

result = set_goal(cat["id"], goal_type, target_amount, target_month)

print(f"\n✓ Goal set: ${target_amount:.2f} on '{cat['name']}'")
if target_month:
    print(f"  Target date: {target_month[:7]}")
print(f"\nOpen YNAB and check your '{cat['name']}' category — you'll see the progress bar.")
