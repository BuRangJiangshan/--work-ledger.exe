"""统计口径：按期 / 批准延期 / 超期三档分列，自然日口径。"""
from __future__ import annotations

import sqlite3
from datetime import date

from ..utils import parse_date, today_str
from .items import serialize_item


def _range_clause(field: str, start: str | None, end: str | None) -> tuple[str, list]:
    clause, params = "", []
    if start:
        clause += f" AND {field} >= ?"
        params.append(start)
    if end:
        clause += f" AND {field} <= ?"
        params.append(end + "T23:59")
    return clause, params


def classify_finish(item: dict) -> str | None:
    """返回 on_time / approved_delay / overdue / no_due / None。"""
    if item.get("status") != "finished" or not item.get("finish_time"):
        return None
    if item.get("due_type") != "clear" or not item.get("original_due_date"):
        return "no_due"
    finish = parse_date(item["finish_time"])
    original = parse_date(item["original_due_date"])
    if not finish or not original:
        return "no_due"
    if item.get("delay_approved") == 1:
        due = parse_date(item.get("due_date")) or original
        return "approved_delay" if finish <= due else "overdue"
    return "on_time" if finish <= original else "overdue"


def compute_stats(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict:
    where = "merged_into IS NULL"
    params: list = []
    rng, rparams = _range_clause("receive_time", start, end)
    where += rng
    params.extend(rparams)

    rows = conn.execute(f"SELECT * FROM items WHERE {where}", params).fetchall()
    items = [dict(r) for r in rows]
    finished = [i for i in items if i["status"] == "finished" and i["finish_time"]]

    on_time = approved_delay = overdue = no_due = 0
    for item in finished:
        cls = classify_finish(item)
        if cls == "on_time":
            on_time += 1
        elif cls == "approved_delay":
            approved_delay += 1
        elif cls == "overdue":
            overdue += 1
        elif cls == "no_due":
            no_due += 1

    denominator = on_time + approved_delay + overdue
    rate = round(on_time / denominator * 100, 1) if denominator else None

    actuals = [i["actual_days"] for i in finished if i.get("actual_days") is not None]
    estimates = [i["estimated_days"] for i in finished if i.get("estimated_days") is not None]
    devs = [
        i["actual_days"] - i["estimated_days"]
        for i in finished
        if i.get("actual_days") is not None and i.get("estimated_days") is not None
    ]
    over_estimate = sum(1 for d in devs if d > 0)

    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for item in items:
        by_source[item["source_type"]] = by_source.get(item["source_type"], 0) + 1
        by_category[item["category"]] = by_category.get(item["category"], 0) + 1

    monthly: dict[str, dict] = {}
    for item in items:
        month = item["receive_time"][:7]
        monthly.setdefault(month, {"month": month, "received": 0, "finished": 0})
        monthly[month]["received"] += 1
        if item["status"] == "finished":
            monthly[month]["finished"] += 1

    instruction_items = conn.execute(
        f"""
        SELECT COUNT(DISTINCT pr.item_id) AS c
        FROM process_records pr JOIN items i ON i.id = pr.item_id
        WHERE pr.action_type = 'instruction' AND i.merged_into IS NULL
        {('AND i.receive_time >= ?' if start else '')}
        {('AND i.receive_time <= ?' if end else '')}
        """,
        [p for p in (start, end + "T23:59" if end else None) if p],
    ).fetchone()["c"]

    overdue_items = [
        serialize_item(conn, r)
        for r in conn.execute(
            "SELECT * FROM items WHERE merged_into IS NULL AND status != 'finished'"
            " AND due_date IS NOT NULL AND date(due_date) < date(?)"
            " ORDER BY due_date ASC",
            (today_str(),),
        ).fetchall()
    ]

    return {
        "start": start,
        "end": end,
        "total_received": len(items),
        "total_finished": len(finished),
        "on_time": on_time,
        "approved_delay": approved_delay,
        "overdue": overdue,
        "no_due": no_due,
        "denominator": denominator,
        "finish_rate": rate,
        "delayed_count": sum(1 for i in items if i.get("delay_approved") == 1),
        "avg_actual_days": round(sum(actuals) / len(actuals), 1) if actuals else None,
        "avg_estimated_days": round(sum(estimates) / len(estimates), 1) if estimates else None,
        "deviation_avg": round(sum(devs) / len(devs), 1) if devs else None,
        "deviation_count": len(devs),
        "over_estimate_count": over_estimate,
        "by_source": [{"name": k, "count": v} for k, v in sorted(by_source.items(), key=lambda x: -x[1])],
        "by_category": [{"name": k, "count": v} for k, v in sorted(by_category.items(), key=lambda x: -x[1])],
        "monthly": sorted(monthly.values(), key=lambda x: x["month"]),
        "leader_instruction_count": instruction_items,
        "overdue_items": overdue_items,
    }
