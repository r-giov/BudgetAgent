#!/usr/bin/env python3
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from gmail_client import GmailClient
from parsers import parse_transaction_email
from ynab_client import YNABClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("sync.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

STATE_FILE = Path("state.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_run": None, "processed_ids": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main():
    required = ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "YNAB_TOKEN", "YNAB_BUDGET_ID", "YNAB_ACCOUNT_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        log.error(f"Missing env vars: {', '.join(missing)}. Check your .env file.")
        return

    state = load_state()
    days_back = 1 if state["last_run"] else 7

    gmail = GmailClient(
        email_addr=os.environ["GMAIL_ADDRESS"],
        app_password=os.environ["GMAIL_APP_PASSWORD"],
    )
    ynab = YNABClient(
        token=os.environ["YNAB_TOKEN"],
        budget_id=os.environ["YNAB_BUDGET_ID"],
        account_id=os.environ["YNAB_ACCOUNT_ID"],
    )

    emails = gmail.fetch_transaction_emails(days_back=days_back)

    processed = set(state.get("processed_ids", []))
    new_transactions = []
    unmatched = []

    for msg_id, subject, sender, body, date in emails:
        if msg_id in processed:
            continue

        txn = parse_transaction_email(subject, sender, body, date, msg_id)
        if txn:
            new_transactions.append(txn)
            processed.add(msg_id)
            sign = "+" if txn["amount"] >= 0 else ""
            log.info(f"  {txn['payee_name']}  {sign}{txn['amount']:.2f}  ({txn['date']})")
        else:
            unmatched.append({"id": msg_id, "subject": subject, "from": sender})

    if new_transactions:
        ynab.post_transactions(new_transactions)

    if unmatched:
        Path("unmatched.json").write_text(json.dumps(unmatched, indent=2))
        log.warning(f"{len(unmatched)} emails had no matching parser — see unmatched.json")

    state["last_run"] = datetime.now().isoformat()
    state["processed_ids"] = list(processed)[-500:]
    save_state(state)

    log.info(f"Done. {len(new_transactions)} transactions posted.")


if __name__ == "__main__":
    main()
