"""通用工具：时间、JSON、编号。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta


def now_str() -> str:
    """当前时间，精确到分钟，ISO8601。"""
    return datetime.now().replace(second=0, microsecond=0).isoformat(timespec="minutes")


def today_str() -> str:
    return date.today().isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip().replace(" ", "T")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    dt = parse_dt(value)
    return dt.date() if dt else None


def day_str(value: str | None) -> str | None:
    d = parse_date(value)
    return d.isoformat() if d else None


def natural_days(start: str | None, end: str | None) -> float | None:
    """自然日差（按日期计算）。"""
    a, b = parse_date(start), parse_date(end)
    if not a or not b:
        return None
    return float((b - a).days)


def normalize_dt(value: str | None, fallback: str | None = None) -> str:
    """把时间统一成 YYYY-MM-DDTHH:MM。"""
    dt = parse_dt(value)
    if not dt:
        dt = parse_dt(fallback) if fallback else datetime.now()
    return dt.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def dumps(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def loads(value, default=None):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def add_days(value: str | None, days: float) -> str | None:
    d = parse_date(value)
    if not d:
        return None
    return (d + timedelta(days=int(days))).isoformat()


def next_item_no(conn, year: int | None = None) -> str:
    year = year or date.today().year
    prefix = f"SX{year}-"
    row = conn.execute(
        "SELECT item_no FROM items WHERE item_no LIKE ? ORDER BY item_no DESC LIMIT 1",
        (prefix + "%",),
    ).fetchone()
    seq = 1
    if row and row["item_no"]:
        try:
            seq = int(row["item_no"].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]
