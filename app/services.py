import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import Any

DATE_FMT = "%d.%m.%Y"
DISPLAY_DATE_FMT = "%d.%m.%Y"
DEFAULT_REMINDER_DAYS = 5


def parse_date(date_str: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(date_str, DATE_FMT).date()
    except ValueError:
        return None


def format_date(date_str: str) -> str:
    parsed = parse_date(date_str)
    if not parsed:
        return date_str
    return parsed.strftime(DISPLAY_DATE_FMT)


def next_server_id(servers: dict[str, dict[str, Any]]) -> str:
    max_idx = 0
    for key in servers:
        if key.startswith("server_"):
            suffix = key.split("_", 1)[1]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return f"server_{max_idx + 1}"


def calculate_next_date(server: dict[str, Any]) -> str:
    base_date = parse_date(str(server.get("next_payment_date", "")))
    if not base_date:
        raise ValueError("Invalid next_payment_date")

    period_type = server.get("period_type")
    if period_type == "monthly":
        new_date = base_date + dt.timedelta(days=30)
    elif period_type == "daily":
        new_date = base_date + dt.timedelta(days=1)
    else:
        raise ValueError("period_type must be monthly or daily")
    return new_date.strftime(DATE_FMT)


def normalize_server_payload(payload: dict[str, Any]) -> dict[str, Any]:
    period_type = payload.get("period_type", "monthly")
    if period_type not in {"monthly", "daily"}:
        period_type = "monthly"

    next_payment_date = str(payload.get("next_payment_date", "")).strip()
    if period_type == "monthly":
        if not parse_date(next_payment_date):
            raise ValueError("invalid date format")
    else:
        next_payment_date = ""

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("name is empty")

    payment_amount = str(payload.get("payment_amount") or "").strip()
    lk_balance = str(payload.get("lk_balance") or "").strip()
    lk_topup_url = str(payload.get("lk_topup_url") or "").strip()

    return {
        "name": name,
        "hosting_name": str(payload.get("hosting_name") or "").strip(),
        "ip_address": str(payload.get("ip_address") or "").strip(),
        "period_type": period_type,
        "payment_amount": payment_amount,
        "next_payment_date": next_payment_date,
        "covered_until": str(payload.get("covered_until") or "").strip(),
        "lk_balance": lk_balance,
        "lk_topup_url": lk_topup_url,
        "last_notified_on": str(payload.get("last_notified_on") or ""),
    }


def due_for_reminder(server: dict[str, Any], today: dt.date, reminder_days: int, ignore_last_notified: bool = False) -> bool:
    period_type = str(server.get("period_type") or "monthly")
    due_date_raw = str(server.get("next_payment_date") or "").strip()
    if period_type == "daily":
        due_date_raw = str(server.get("covered_until") or "").strip()
    due_date = parse_date(due_date_raw)
    if not due_date:
        return False
    last_notified_on = parse_date(str(server.get("last_notified_on", "")))
    if not ignore_last_notified and last_notified_on == today:
        return False
    return today + dt.timedelta(days=reminder_days) >= due_date


def parse_decimal_value(raw: Any) -> Decimal | None:
    text = str(raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return value


def balance_coverage_until(server: dict[str, Any], today: dt.date | None = None) -> dt.date | None:
    current_day = today or dt.date.today()
    balance = parse_decimal_value(server.get("lk_balance"))
    amount = parse_decimal_value(server.get("payment_amount"))
    period_type = str(server.get("period_type") or "monthly")
    if balance is None or amount is None or amount <= 0:
        return None

    if period_type == "daily":
        paid_days = int(balance // amount)
        if paid_days <= 0:
            return None
        return current_day + dt.timedelta(days=paid_days - 1)

    due_date = parse_date(str(server.get("next_payment_date", "")))
    if not due_date:
        return None
    next_charge = due_date
    remainder = balance
    while remainder >= amount:
        remainder -= amount
        next_charge += dt.timedelta(days=30)
    return next_charge - dt.timedelta(days=1)


def balance_coverage_until_str(server: dict[str, Any], today: dt.date | None = None) -> str:
    covered_until = balance_coverage_until(server, today=today)
    if not covered_until:
        return ""
    return covered_until.strftime(DATE_FMT)


TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def is_valid_time_hhmm(value: str) -> bool:
    return bool(TIME_RE.match(value.strip()))
