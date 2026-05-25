#!/usr/bin/env python3
"""
One-time bulk import of your May 2026 transactions into YNAB.
Reads unmatched.json (Hermes transaction history) and posts everything
with proper categories.
"""
import json
import os
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE        = "https://api.ynab.com/v1"
TOKEN       = os.environ["YNAB_TOKEN"]
BUDGET_ID   = os.environ["YNAB_BUDGET_ID"]
ACCOUNT_ID  = os.environ["YNAB_ACCOUNT_ID"]  # Scotia Chequing
HEADERS     = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Category ID map (from your YNAB) ──────────────────────────────
# Debt Reduction
CAT_BUSINESS_DEBT   = "adf14b33-767c-492d-8912-293682aecca9"
CAT_PERSONAL_DEBT   = "c91cf357-c5e1-4737-9e22-0ae33c05b7eb"
CAT_READY_TO_ASSIGN = "a5848111-1c23-4089-86de-ad0272678652"
CAT_UNCATEGORIZED   = "75f4c3ba-81b1-4d0a-aa19-9d4d13ec425f"

# Bills
CAT_RENT            = "f425aeec-b00c-4b9d-b8db-7276cd5e876a"
CAT_JPS             = "ced1fca1-3368-426d-bf46-7ed09dc392aa"
CAT_NWC             = "c30a2e96-78c1-46ea-9a49-24ff7e33f126"
CAT_PHONE_INTERNET  = "8027284a-3883-48d9-ad21-dcf8747b092c"

# Needs / Savings
CAT_EDJ_PARTNER     = "fe5ab207-7039-44af-91be-b38ee283a618"
CAT_GROCERIES       = "43a48537-c1f7-4813-8a50-d75687bd325d"
CAT_TRANSPORT       = "685a5e1b-9c47-49aa-b89b-505d0e629bf5"
CAT_EMERGENCY_FUND  = "bd6777d4-8188-4425-a590-5152effd9f25"

# Wants
CAT_HELPING_FAMILY  = "9027c1ef-e907-45d9-847a-0a3e8f269edd"
CAT_EDUCATION       = "df034f7b-4ea4-4429-8e88-2891b5849843"
CAT_EATING_OUT      = "4ceed74b-74de-49ae-9b8c-53caea8e8def"
CAT_CANNABIS        = "4529b794-f906-4666-84ba-89bc633776a2"
CAT_ENTERTAINMENT   = "7dd8cd33-c892-4a30-badb-fd9ec37b62e6"
CAT_HOBBIES         = "0fc2bdf2-30a5-49bb-a8ec-9ce6c09ebb90"
CAT_GIFTS           = "2103af91-8d72-407b-84e6-efbe202ef0c8"
CAT_SHOPPING        = "37531269-fac7-44ba-995b-6853bb7ddd58"
CAT_TRAVEL          = "e97166d2-6f6a-4b6c-ac5d-bc3be619f2a0"

# Investing / Trading
CAT_PROP_FIRMS      = "578373b4-5bcc-497f-997a-b918fda554af"
CAT_TRADING_SYSTEMS = "a899ec35-f6e2-476b-b17c-ce7de2a4b441"

# Savings
CAT_SAVINGS         = "3df76601-eea2-4a5a-a0ed-6c841847ea93"


# ── Payee → category mapping ──────────────────────────────────────
def resolve_category(payee: str, json_category: str) -> str:
    p = payee.lower()

    if "rosalie" in p or "rent" in p:         return CAT_RENT
    if "jps" in p or "jamaica public" in p:   return CAT_JPS
    if "nwc" in p or "national water" in p:   return CAT_NWC
    if "digicel" in p or "flow" in p:         return CAT_PHONE_INTERNET
    if "dominique" in p or "edj" in p:        return CAT_EDJ_PARTNER
    if "ncb" in p and "self" in p:            return CAT_BUSINESS_DEBT
    if "cfa" in p or "paula" in p:            return CAT_EDUCATION
    if "gumroad" in p or "ea pro" in p:       return CAT_TRADING_SYSTEMS
    if "5ers" in p or "prop" in p:            return CAT_PROP_FIRMS
    if "pandora" in p:                        return CAT_GIFTS
    if "aunty" in p or "colleen" in p:        return CAT_HELPING_FAMILY
    if "linnaeus" in p or "cannabis" in p:    return CAT_CANNABIS
    if "golf" in p or "instructor" in p:      return CAT_HOBBIES
    if "dennis" in p or "cabbage" in p or "box food" in p: return CAT_EATING_OUT

    # Fall back to JSON category hint
    jc = json_category.lower()
    if "housing" in jc:        return CAT_RENT
    if "utilities" in jc:      return CAT_JPS
    if "education" in jc:      return CAT_EDUCATION
    if "prop trading" in jc:   return CAT_PROP_FIRMS
    if "trading tools" in jc:  return CAT_TRADING_SYSTEMS
    if "gifts" in jc:          return CAT_GIFTS
    if "household" in jc:      return CAT_HELPING_FAMILY
    if "personal" in jc:       return CAT_CANNABIS
    if "leisure" in jc:        return CAT_HOBBIES
    if "food" in jc or "dining" in jc: return CAT_EATING_OUT
    if "debt" in jc:           return CAT_BUSINESS_DEBT
    if "savings" in jc:        return CAT_SAVINGS

    return CAT_UNCATEGORIZED


def make_import_id(payee, amount, date):
    key = f"bulk:{payee}:{amount}:{date}"
    return f"bi:{hashlib.md5(key.encode()).hexdigest()[:16]}"


# ── Load transactions ─────────────────────────────────────────────
data = json.loads(Path("transactions_may2026.json").read_text())
transactions = []

for account_key, account in data["accounts"].items():
    for txn in account["transactions"]:
        payee    = txn["payee"]
        amount   = txn["amount"]          # already signed (negative = outflow)
        date     = txn["date"]
        memo     = txn.get("memo", "")
        cleared  = txn.get("cleared", False)
        category = txn.get("category", "UNCATEGORIZED")

        # Skip pending unknowns — wait until they clear
        if "Unknown" in payee or txn.get("estimated") and "unknown" in memo.lower():
            print(f"  SKIP (pending): {payee} {amount}")
            continue

        # Income goes to Ready to Assign (no category_id needed for inflows)
        cat_id = None
        if amount > 0:
            cat_id = CAT_READY_TO_ASSIGN
        else:
            cat_id = resolve_category(payee, category)

        transactions.append({
            "account_id":  ACCOUNT_ID,
            "date":        date,
            "amount":      int(amount * 1000),   # milliunits
            "payee_name":  payee[:50],
            "memo":        memo[:200],
            "cleared":     "cleared" if cleared else "uncleared",
            "category_id": cat_id,
            "import_id":   make_import_id(payee, amount, date),
        })

# ── Preview ───────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"  {'DATE':<12} {'AMOUNT':>12}  {'PAYEE':<30}  CATEGORY")
print(f"{'─'*70}")
for t in transactions:
    sign   = "+" if t["amount"] > 0 else ""
    amount = t["amount"] / 1000
    print(f"  {t['date']:<12} {sign}{amount:>10.2f}  {t['payee_name']:<30}  {t['category_id'][:8]}...")
print(f"{'─'*70}")
print(f"  {len(transactions)} transactions ready | 5 pending holds skipped\n")

confirm = input("Post these to YNAB? [y/n]: ").strip().lower()
if confirm != "y":
    print("Aborted.")
    exit(0)

# ── Post to YNAB ──────────────────────────────────────────────────
r = requests.post(
    f"{BASE}/budgets/{BUDGET_ID}/transactions",
    headers=HEADERS,
    json={"transactions": transactions},
)

if r.status_code == 201:
    data = r.json()["data"]
    created = len(data.get("transaction_ids", []))
    dupes   = len(data.get("duplicate_import_ids", []))
    print(f"\n✓ {created} transactions posted, {dupes} duplicates skipped.")
    print("Check YNAB — your May budget should now reflect your actual spending.")
else:
    print(f"Error {r.status_code}: {r.text}")
