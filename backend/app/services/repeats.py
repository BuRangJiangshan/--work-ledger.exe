"""重复任务规则与自动生成。"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, time, timedelta

from ..audit import log_audit
from ..utils import dumps, loads, now_str, parse_dt
from .items import create_item


def serialize_rule(row) -> dict:
    d = dict(row)
    d["item_template"] = loads(d.get("item_template"), {}) or {}
    d["schedule"] = loads(d.get("schedule_expr"), {}) or {}
    d["enabled"] = bool(d.get("enabled"))
    return d


def list_rules(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM repeat_rules ORDER BY id DESC").fetchall()
    return [serialize_rule(r) for r in rows]


def _parse_time(value: str | None) -> time:
    try:
        hh, mm = (value or "09:00").split(":")[:2]
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return time(9, 0)


def fixed_next_run(schedule: dict, base: datetime) -> datetime:
    freq = (schedule or {}).get("freq", "daily")
    t = _parse_time((schedule or {}).get("time"))
    if freq == "weekly":
        weekday = int((schedule or {}).get("weekday", 0)) % 7
        days = (weekday - base.weekday()) % 7
        candidate = datetime.combine(base.date() + timedelta(days=days), t)
        if candidate <= base:
            candidate += timedelta(days=7)
        return candidate
    if freq == "monthly":
        day = int((schedule or {}).get("day", 1))
        year, month = base.year, base.month
        last = calendar.monthrange(year, month)[1]
        candidate = datetime.combine(date(year, month, min(day, last)), t)
        if candidate <= base:
            month += 1
            if month > 12:
                month, year = 1, year + 1
            last = calendar.monthrange(year, month)[1]
            candidate = datetime.combine(date(year, month, min(day, last)), t)
        return candidate
    candidate = datetime.combine(base.date(), t)
    if candidate <= base:
        candidate += timedelta(days=1)
    return candidate


def create_rule(conn: sqlite3.Connection, data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("规则名称不能为空")
    trigger_type = data.get("trigger_type")
    if trigger_type not in ("fixed", "after_done"):
        raise ValueError("触发方式必须是固定周期或完成后 N 天")
    template = data.get("item_template") or {}
    if not isinstance(template, dict) or not (template.get("title") or "").strip():
        raise ValueError("事项模板必须包含标题")
    schedule = data.get("schedule") or {}
    after_days = data.get("after_done_days")
    if trigger_type == "after_done" and (after_days is None or int(after_days) <= 0):
        raise ValueError("完成后触发必须填写大于 0 的天数")
    next_run = (
        fixed_next_run(schedule, datetime.now()).isoformat(timespec="minutes")
        if trigger_type == "fixed"
        else now_str()
    )
    cur = conn.execute(
        """
        INSERT INTO repeat_rules(name, item_template, trigger_type, schedule_expr,
            after_done_days, backlog_strategy, next_run_time, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            dumps(template),
            trigger_type,
            dumps(schedule) if schedule else None,
            int(after_days) if after_days else None,
            data.get("backlog_strategy") or "keep_all",
            next_run,
            0 if data.get("enabled") is False else 1,
            now_str(),
        ),
    )
    log_audit(conn, "repeat_rule", cur.lastrowid, "created", None, name)
    return serialize_rule(
        conn.execute("SELECT * FROM repeat_rules WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def update_rule(conn: sqlite3.Connection, rule_id: int, data: dict) -> dict:
    row = conn.execute("SELECT * FROM repeat_rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None:
        raise KeyError(f"规则 {rule_id} 不存在")
    old = dict(row)
    new = dict(old)
    if "name" in data and data["name"]:
        new["name"] = data["name"].strip()
    if "item_template" in data and data["item_template"]:
        new["item_template"] = dumps(data["item_template"])
    if "trigger_type" in data and data["trigger_type"] in ("fixed", "after_done"):
        new["trigger_type"] = data["trigger_type"]
    if "schedule" in data:
        new["schedule_expr"] = dumps(data["schedule"]) if data["schedule"] else None
        if new["trigger_type"] == "fixed":
            new["next_run_time"] = fixed_next_run(
                data["schedule"] or {}, datetime.now()
            ).isoformat(timespec="minutes")
    if "after_done_days" in data:
        new["after_done_days"] = (
            int(data["after_done_days"]) if data["after_done_days"] else None
        )
    if "backlog_strategy" in data:
        new["backlog_strategy"] = data["backlog_strategy"]
    if "enabled" in data:
        new["enabled"] = 0 if data["enabled"] is False else 1
    conn.execute(
        "UPDATE repeat_rules SET name = ?, item_template = ?, trigger_type = ?,"
        " schedule_expr = ?, after_done_days = ?, backlog_strategy = ?,"
        " next_run_time = ?, enabled = ? WHERE id = ?",
        (
            new["name"],
            new["item_template"],
            new["trigger_type"],
            new["schedule_expr"],
            new["after_done_days"],
            new["backlog_strategy"],
            new["next_run_time"],
            new["enabled"],
            rule_id,
        ),
    )
    log_audit(conn, "repeat_rule", rule_id, "updated", old["name"], new["name"])
    return serialize_rule(
        conn.execute("SELECT * FROM repeat_rules WHERE id = ?", (rule_id,)).fetchone()
    )


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    row = conn.execute("SELECT * FROM repeat_rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None:
        raise KeyError(f"规则 {rule_id} 不存在")
    conn.execute("DELETE FROM repeat_rules WHERE id = ?", (rule_id,))
    log_audit(conn, "repeat_rule", rule_id, "deleted", row["name"], None)


def _has_unfinished(conn: sqlite3.Connection, rule_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM items WHERE repeat_rule_id = ? AND merged_into IS NULL"
        " AND status != 'finished' LIMIT 1",
        (rule_id,),
    ).fetchone()
    return row is not None


def _generate(conn: sqlite3.Connection, rule: dict) -> int | None:
    template = loads(rule["item_template"], {}) or {}
    template = dict(template)
    template["title"] = str(template.get("title", rule["name"])).replace(
        "{date}", datetime.now().strftime("%Y-%m-%d")
    )
    template.setdefault("category", "日常事务")
    template.setdefault("source_type", "其他")
    template["repeat_rule_id"] = rule["id"]
    item = create_item(conn, template, op_source="repeat")
    return item["id"]


def process_due_rules(conn: sqlite3.Connection, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    created: list[int] = []
    rules = conn.execute(
        "SELECT * FROM repeat_rules WHERE enabled = 1 ORDER BY id"
    ).fetchall()
    for row in rules:
        rule = dict(row)
        if rule["trigger_type"] == "fixed":
            schedule = loads(rule.get("schedule_expr"), {}) or {}
            next_run = parse_dt(rule.get("next_run_time"))
            if next_run is None:
                conn.execute(
                    "UPDATE repeat_rules SET next_run_time = ? WHERE id = ?",
                    (fixed_next_run(schedule, now).isoformat(timespec="minutes"), rule["id"]),
                )
                continue
            guard = 0
            while next_run <= now and guard < 20:
                if rule["backlog_strategy"] == "latest_only" and _has_unfinished(conn, rule["id"]):
                    pass
                else:
                    item_id = _generate(conn, rule)
                    if item_id:
                        created.append(item_id)
                next_run = fixed_next_run(schedule, next_run + timedelta(minutes=1))
                conn.execute(
                    "UPDATE repeat_rules SET next_run_time = ? WHERE id = ?",
                    (next_run.isoformat(timespec="minutes"), rule["id"]),
                )
                guard += 1
        else:
            last = conn.execute(
                "SELECT * FROM items WHERE repeat_rule_id = ? ORDER BY id DESC LIMIT 1",
                (rule["id"],),
            ).fetchone()
            if last is None:
                item_id = _generate(conn, rule)
                if item_id:
                    created.append(item_id)
                continue
            if last["status"] != "finished" or not last["finish_time"]:
                continue
            finish = parse_dt(last["finish_time"])
            if finish is None:
                continue
            due = finish + timedelta(days=int(rule["after_done_days"] or 0))
            conn.execute(
                "UPDATE repeat_rules SET next_run_time = ? WHERE id = ?",
                (due.isoformat(timespec="minutes"), rule["id"]),
            )
            if due <= now:
                item_id = _generate(conn, rule)
                if item_id:
                    created.append(item_id)
    return {"created": created, "count": len(created)}
