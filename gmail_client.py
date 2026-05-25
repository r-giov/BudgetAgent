import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

SEARCH_SUBJECTS = [
    "transaction", "payment", "receipt", "alert",
    "you sent", "you received", "charged", "debit",
    "credit", "withdrawal", "deposit",
]

SEARCH_SENDERS = ["paypal", "cashapp", "venmo", "cash.app", "square.com"]


class GmailClient:
    def __init__(self, email_addr: str, app_password: str):
        self.email_addr = email_addr
        self.app_password = app_password

    def _decode_str(self, s):
        if not s:
            return ""
        parts = decode_header(s)
        result = []
        for part, enc in parts:
            if isinstance(part, bytes):
                result.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)

    def _get_body(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace")
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
        return ""

    def fetch_transaction_emails(self, days_back: int = 1):
        results = []
        since = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(self.email_addr, self.app_password)
        mail.select("inbox")

        search_terms = (
            [f'(SINCE {since} SUBJECT "{s}")' for s in SEARCH_SUBJECTS]
            + [f'(SINCE {since} FROM "{s}")' for s in SEARCH_SENDERS]
        )

        all_ids = set()
        for term in search_terms:
            _, data = mail.search(None, term)
            if data[0]:
                all_ids.update(data[0].split())

        log.info(f"Found {len(all_ids)} candidate emails (last {days_back}d)")

        for msg_id in all_ids:
            _, data = mail.fetch(msg_id, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = self._decode_str(msg.get("Subject", ""))
            sender = msg.get("From", "")
            date_str = msg.get("Date", "")
            body = self._get_body(msg)

            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.now()

            results.append((msg_id.decode(), subject, sender, body, date))

        mail.logout()
        return results
