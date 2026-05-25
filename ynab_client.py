import requests
import logging

log = logging.getLogger(__name__)

BASE = "https://api.ynab.com/v1"


class YNABClient:
    def __init__(self, token: str, budget_id: str, account_id: str):
        self.budget_id = budget_id
        self.account_id = account_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def list_budgets(self):
        r = requests.get(f"{BASE}/budgets", headers=self.headers)
        r.raise_for_status()
        return r.json()["data"]["budgets"]

    def list_accounts(self):
        r = requests.get(f"{BASE}/budgets/{self.budget_id}/accounts", headers=self.headers)
        r.raise_for_status()
        return r.json()["data"]["accounts"]

    def post_transactions(self, transactions: list) -> dict:
        payload = {
            "transactions": [
                {
                    "account_id": self.account_id,
                    "date": t["date"],
                    "amount": int(t["amount"] * 1000),  # YNAB uses milliunits
                    "payee_name": t["payee_name"][:50],
                    "memo": t.get("memo", "")[:200],
                    "import_id": t.get("import_id"),
                    "cleared": "cleared",
                }
                for t in transactions
            ]
        }

        r = requests.post(
            f"{BASE}/budgets/{self.budget_id}/transactions",
            headers=self.headers,
            json=payload,
        )
        r.raise_for_status()
        data = r.json()["data"]
        created = len(data.get("transaction_ids", []))
        dupes = len(data.get("duplicate_import_ids", []))
        log.info(f"YNAB: {created} created, {dupes} duplicates skipped")
        return data
