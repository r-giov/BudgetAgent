import re
import hashlib
import logging
from datetime import datetime

log = logging.getLogger(__name__)


def _make_import_id(email_id: str, amount: float, date: datetime) -> str:
    key = f"{email_id}:{amount:.2f}:{date.strftime('%Y-%m-%d')}"
    return f"es:{hashlib.md5(key.encode()).hexdigest()[:16]}"


def _clean_amount(s: str) -> float:
    return float(re.sub(r"[,$€£\s]", "", s))


def _is_outflow(text: str) -> bool:
    return bool(re.search(
        r"\b(sent|paid|charged|purchase|debit|withdrawal|payment)\b",
        text, re.IGNORECASE
    ))


# ── PayPal ────────────────────────────────────────────────────────────────────

def parse_paypal(subject, sender, body, date, email_id):
    if "paypal" not in sender.lower() and "paypal" not in subject.lower():
        return None

    text = subject + " " + body
    m = re.search(r"\$\s*([\d,]+\.?\d{0,2})", text)
    if not m:
        return None

    amount = _clean_amount(m.group(1))
    payee_m = re.search(r"\b(?:to|from)\s+([A-Za-z][A-Za-z\s\-\.]{1,40}?)(?:\s+on|\s+for|\.|,|$)", text, re.IGNORECASE)
    payee = payee_m.group(1).strip() if payee_m else "PayPal"

    sign = -1 if _is_outflow(text) else 1
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": f"PayPal – {subject[:80]}",
        "import_id": _make_import_id(email_id, amount, date),
    }


# ── CashApp ───────────────────────────────────────────────────────────────────

def parse_cashapp(subject, sender, body, date, email_id):
    is_cashapp = any(k in sender.lower() for k in ("cash.app", "cashapp", "square.com"))
    is_cashapp = is_cashapp or any(k in subject.lower() for k in ("cash app", "cashapp"))
    if not is_cashapp:
        return None

    text = subject + " " + body
    m = re.search(r"\$\s*([\d,]+\.?\d{0,2})", text)
    if not m:
        return None

    amount = _clean_amount(m.group(1))
    payee_m = re.search(r"\b(?:to|from)\s+(\$?\w[\w\s]{1,30}?)(?:\s+on|\s+for|\.|$)", text, re.IGNORECASE)
    payee = payee_m.group(1).strip() if payee_m else "CashApp"

    sign = -1 if _is_outflow(text) else 1
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": f"CashApp – {subject[:80]}",
        "import_id": _make_import_id(email_id, amount, date),
    }


# ── Venmo ─────────────────────────────────────────────────────────────────────

def parse_venmo(subject, sender, body, date, email_id):
    if "venmo" not in sender.lower() and "venmo" not in subject.lower():
        return None

    text = subject + " " + body
    m = re.search(r"\$\s*([\d,]+\.?\d{0,2})", text)
    if not m:
        return None

    amount = _clean_amount(m.group(1))
    payee_m = re.search(r"\b(?:paid|from|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    payee = payee_m.group(1) if payee_m else "Venmo"

    sign = -1 if _is_outflow(text) else 1
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": f"Venmo – {subject[:80]}",
        "import_id": _make_import_id(email_id, amount, date),
    }


# ── Generic bank alert ────────────────────────────────────────────────────────

def parse_bank_alert(subject, sender, body, date, email_id):
    text = (subject + " " + body).lower()
    bank_kw = ("alert", "transaction", "debit", "credit", "charged",
               "withdrawal", "deposit", "payment", "purchase")
    if not any(k in text for k in bank_kw):
        return None

    # Currency amount — support USD/JMD/CAD
    m = re.search(r"(?:usd|jmd|cad|gbp)?\s*\$?\s*([\d,]+\.?\d{0,2})", body + " " + subject, re.IGNORECASE)
    if not m:
        return None

    amount = _clean_amount(m.group(1))
    if amount < 0.01:
        return None

    is_credit = bool(re.search(r"\b(credit|deposit|received|refund|inflow)\b", text))
    sign = 1 if is_credit else -1

    # Extract merchant name
    payee = "Bank Transaction"
    for pat in (
        r"(?:at|merchant[:\s]+)\s*([A-Za-z][A-Za-z0-9\s\*&\-\.]{2,40}?)(?:\s+on\b|\s+for\b|\s+\$|\.|,|$)",
        r"(?:purchase at|charged by)\s+([A-Za-z].{2,40}?)(?:\s+on\b|\.|$)",
    ):
        pm = re.search(pat, body, re.IGNORECASE)
        if pm:
            payee = pm.group(1).strip()[:50]
            break

    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": subject[:100],
        "import_id": _make_import_id(email_id, amount, date),
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

PARSERS = [parse_paypal, parse_cashapp, parse_venmo, parse_bank_alert]


def parse_transaction_email(subject, sender, body, date, email_id):
    for parser in PARSERS:
        try:
            result = parser(subject, sender, body, date, email_id)
            if result:
                return result
        except Exception as e:
            log.debug(f"{parser.__name__} error: {e}")
    return None
