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


def _extract_note(body: str) -> str:
    """Pull out a payment note/memo/description from the email body."""
    for pat in (
        r"(?:note|memo|message|description|for)[:\s]+[\"']?([^\n\r\"']{3,80})[\"']?",
        r"(?:what's it for|purpose)[:\s]+([^\n\r]{3,80})",
    ):
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            note = m.group(1).strip().rstrip(".")
            # Ignore generic/useless notes
            if not re.match(r"^(n/?a|none|-)$", note, re.IGNORECASE):
                return note
    return ""


def _extract_bank_name(sender: str) -> str:
    """Best-effort bank name from sender email domain."""
    domain_map = {
        "scotiabank": "Scotiabank",
        "ncb": "NCB",
        "jmmb": "JMMB",
        "sagicor": "Sagicor",
        "cibc": "CIBC",
        "bns": "Scotiabank",
        "chase": "Chase",
        "bofa": "Bank of America",
        "bankofamerica": "Bank of America",
        "wellsfargo": "Wells Fargo",
        "citi": "Citibank",
        "capitalone": "Capital One",
        "barclays": "Barclays",
    }
    sender_lower = sender.lower()
    for key, name in domain_map.items():
        if key in sender_lower:
            return name
    # Fall back to domain name capitalised
    m = re.search(r"@([\w\-]+)\.", sender_lower)
    if m:
        return m.group(1).replace("-", " ").title()
    return "Bank"


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
    direction = "Sent to" if sign == -1 else "Received from"
    note = _extract_note(body)
    memo = f"PayPal: {direction} {payee}"
    if note:
        memo += f" – {note}"
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": memo[:200],
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
    direction = "Sent to" if sign == -1 else "Received from"
    note = _extract_note(body)
    memo = f"CashApp: {direction} {payee}"
    if note:
        memo += f" – {note}"
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": memo[:200],
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
    direction = "Paid" if sign == -1 else "Received from"
    note = _extract_note(body)
    memo = f"Venmo: {direction} {payee}"
    if note:
        memo += f" – {note}"
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": memo[:200],
        "import_id": _make_import_id(email_id, amount, date),
    }


# ── Generic bank alert ────────────────────────────────────────────────────────

# Senders that are almost certainly financial institutions
FINANCIAL_SENDER_PATTERNS = re.compile(
    r"(scotiabank|ncb|jmmb|sagicor|cibc|chase|paypal|cashapp|venmo|"
    r"bankofamerica|wellsfargo|citibank|capitalone|barclays|alert|"
    r"notification|noreply.*bank|bank.*noreply|transactions@|statement@)",
    re.IGNORECASE,
)

# Subject lines that strongly indicate a real transaction alert
FINANCIAL_SUBJECT_PATTERNS = re.compile(
    r"\b(transaction alert|debit alert|credit alert|payment alert|"
    r"account alert|your receipt|purchase confirmation|payment received|"
    r"payment sent|funds received|funds sent|withdrawal confirmed|"
    r"deposit confirmed|low balance|transaction notification)\b",
    re.IGNORECASE,
)

MAX_SANE_AMOUNT = 500_000  # anything above this is almost certainly a parse error


def parse_bank_alert(subject, sender, body, date, email_id):
    # Must come from a financial sender OR have a very specific financial subject
    if not FINANCIAL_SENDER_PATTERNS.search(sender) and not FINANCIAL_SUBJECT_PATTERNS.search(subject):
        return None

    text = (subject + " " + body).lower()

    # Amount must have an explicit currency symbol — no bare numbers
    m = re.search(
        r"(?:(?:usd|jmd|cad|gbp|j)\s*)?\$\s*([\d,]+\.?\d{0,2})",
        body + " " + subject,
        re.IGNORECASE,
    )
    if not m:
        return None

    amount = _clean_amount(m.group(1))
    if amount < 0.01 or amount > MAX_SANE_AMOUNT:
        return None

    is_credit = bool(re.search(r"\b(credit|deposit|received|refund|inflow)\b", text))
    sign = 1 if is_credit else -1

    # Extract merchant — strict patterns only
    payee = "Bank Transaction"
    for pat in (
        r"(?:at|merchant[:\s]+)\s*([A-Za-z][A-Za-z0-9\s\*&\-\.]{2,40}?)(?:\s+on\b|\s+for\b|\s+\$|\.|,|$)",
        r"(?:purchase at|charged by|paid to)\s+([A-Za-z][A-Za-z0-9\s\-\.]{2,40}?)(?:\s+on\b|\.|$)",
    ):
        pm = re.search(pat, body, re.IGNORECASE)
        if pm:
            candidate = pm.group(1).strip()
            # Reject if it looks like sentence fragments (too many lowercase common words)
            if len(candidate) <= 50 and not re.search(r"\b(the|and|for|from|your|this|that|with|have|been)\b", candidate, re.IGNORECASE):
                payee = candidate
                break

    bank = _extract_bank_name(sender)
    txn_type = "Deposit" if is_credit else "Purchase" if re.search(r"\bpurchase\b", text) else "Debit"
    memo = f"{bank}: {txn_type}"
    if payee != "Bank Transaction":
        memo += f" – {payee}"
    note = _extract_note(body)
    if note:
        memo += f" ({note})"
    return {
        "payee_name": payee,
        "amount": sign * amount,
        "date": date.strftime("%Y-%m-%d"),
        "memo": memo[:200],
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
