"""事项、过程记录、关联关系的业务逻辑。"""
from __future__ import annotations

import sqlite3
from datetime import date

from ..audit import log_audit, log_field_changes
from ..status import (
    ACTION_LABEL,
    ACTION_REQUIRED_FIELDS,
    ACTION_TARGET_STATUS,
    ACTION_TYPES,
    CATEGORIES,
    RELATION_LABEL,
    STATUS_LABEL,
    ensure_status_transition,
)
from ..utils import (
    add_days,
    day_str,
    dumps,
    loads,
    natural_days,
    next_item_no,
    normalize_dt,
    now_str,
    parse_date,
)
from .settings import get_setting

_ACTION_VALUES = {a["value"] for a in ACTION_TYPES}
_RELATION_VALUES = set(RELATION_LABEL)

ITEM_EDITABLE_FIELDS = [
    "title", "category", "source_type", "source_no", "source_unit",
    "receive_time", "receive_method", "due_date", "due_type", "estimated_days",
    "status", "handle_mode", "current_handler", "finish_time", "finish_method",
    "finish_summary", "actual_days", "delay_reason", "delay_applied_to",
    "delay_approved", "pinned", "attachments",
]

_DATE_FIELDS = {"due_date", "original_due_date"}


def get_item_row(conn: sqlite3.Connection, item_id: int):
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise KeyError(f"事项 {item_id} 不存在")
    return row


def _merged_sources(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, item_no, title, status, merged_into FROM items"
        " WHERE merged_into = ? ORDER BY id",
        (item_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "item_no": r["item_no"],
            "title": r["title"],
            "status": r["status"],
            "status_label": STATUS_LABEL.get(r["status"], r["status"]),
        }
        for r in rows
    ]


def serialize_item(conn: sqlite3.Connection, row) -> dict:
    item = dict(row)
    item["attachments"] = loads(item.get("attachments"), []) or []
    item["status_label"] = STATUS_LABEL.get(item.get("status"), item.get("status"))
    item["remaining_days"] = None
    item["reminder"] = "none"
    item["overdue"] = False
    if item.get("status") != "finished" and item.get("due_date") and not item.get("merged_into"):
        due = parse_date(item["due_date"])
        if due:
            days = (due - date.today()).days
            item["remaining_days"] = days
            if days <= 0:
                item["reminder"] = "red"
            elif days <= 3:
                item["reminder"] = "yellow"
            else:
                item["reminder"] = "green"
            item["overdue"] = days < 0
    item["merged_sources"] = _merged_sources(conn, item["id"])
    return item


def _relations(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT r.id, r.master_item_id, r.related_item_id, r.relation_type,
               r.created_time, r.created_method, r.note,
               m.item_no AS master_item_no, m.title AS master_title, m.status AS master_status,
               c.item_no AS related_item_no, c.title AS related_title, c.status AS related_status
        FROM item_relations r
        JOIN items m ON m.id = r.master_item_id
        JOIN items c ON c.id = r.related_item_id
        WHERE r.master_item_id = ? OR r.related_item_id = ?
        ORDER BY r.id DESC
        """,
        (item_id, item_id),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["relation_label"] = RELATION_LABEL.get(d["relation_type"], d["relation_type"])
        d["direction"] = "master" if d["master_item_id"] == item_id else "related"
        other_id = d["related_item_id"] if d["direction"] == "master" else d["master_item_id"]
        other_no = d["related_item_no"] if d["direction"] == "master" else d["master_item_no"]
        other_title = d["related_title"] if d["direction"] == "master" else d["master_title"]
        d["other"] = {"id": other_id, "item_no": other_no, "title": other_title}
        result.append(d)
    return result


def _record_dict(row) -> dict:
    d = dict(row)
    d["report_channels"] = loads(d.get("report_channels"), []) or []
    d["attachments"] = loads(d.get("attachments"), []) or []
    d["action_label"] = ACTION_LABEL.get(d.get("action_type"), d.get("action_type"))
    return d


def list_records(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT pr.*, oi.item_no AS origin_item_no
        FROM process_records pr
        LEFT JOIN items oi ON oi.id = pr.origin_item_id
        WHERE pr.item_id = ?
        ORDER BY pr.action_time DESC, pr.id DESC
        """,
        (item_id,),
    ).fetchall()
    return [_record_dict(r) for r in rows]


def list_audit(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM audit_history
        WHERE (obj_type = 'item' AND obj_id = ?)
           OR (obj_type = 'process_record' AND obj_id IN
               (SELECT id FROM process_records WHERE item_id = ?))
        ORDER BY op_time DESC, id DESC
        """,
        (item_id, item_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_item_detail(conn: sqlite3.Connection, item_id: int) -> dict:
    row = get_item_row(conn, item_id)
    item = serialize_item(conn, row)
    item["relations"] = _relations(conn, item_id)
    item["records"] = list_records(conn, item_id)
    item["audit"] = list_audit(conn, item_id)
    if item.get("merged_into"):
        master = conn.execute(
            "SELECT id, item_no, title FROM items WHERE id = ?", (item["merged_into"],)
        ).fetchone()
        item["merged_into_item"] = dict(master) if master else None
    else:
        item["merged_into_item"] = None
    return item


def list_items(conn: sqlite3.Connection, filters: dict) -> dict:
    where = []
    params: list = []
    include_merged = bool(filters.get("include_merged"))
    if not include_merged:
        where.append("merged_into IS NULL")
    if filters.get("q"):
        q = f"%{filters['q'].strip()}%"
        where.append(
            "(title LIKE ? OR source_no LIKE ? OR source_unit LIKE ?"
            " OR current_handler LIKE ? OR item_no LIKE ?)"
        )
        params.extend([q, q, q, q, q])
    for field, column in (
        ("category", "category"),
        ("source_type", "source_type"),
        ("status", "status"),
        ("handle_mode", "handle_mode"),
    ):
        value = filters.get(field)
        if value:
            values = [v for v in str(value).split(",") if v]
            placeholders = ",".join("?" for _ in values)
            where.append(f"{column} IN ({placeholders})")
            params.extend(values)
    if filters.get("pinned"):
        where.append("pinned = 1")
    if filters.get("due_from"):
        where.append("due_date >= ?")
        params.append(filters["due_from"])
    if filters.get("due_to"):
        where.append("due_date <= ?")
        params.append(filters["due_to"])
    if filters.get("receive_from"):
        where.append("receive_time >= ?")
        params.append(filters["receive_from"])
    if filters.get("receive_to"):
        where.append("receive_time <= ?")
        params.append(filters["receive_to"] + "T23:59")
    if filters.get("finished_from"):
        where.append("finish_time >= ?")
        params.append(filters["finished_from"])
    if filters.get("finished_to"):
        where.append("finish_time <= ?")
        params.append(filters["finished_to"] + "T23:59")
    if filters.get("overdue") == "1":
        where.append(
            "status != 'finished' AND due_date IS NOT NULL AND date(due_date) < date('now')"
        )
    if filters.get("instruction") == "1":
        where.append(
            "id IN (SELECT item_id FROM process_records WHERE action_type = 'instruction')"
        )
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""

    sort = filters.get("sort") or "recent"
    order_map = {
        "recent": "pinned DESC, created_at DESC, id DESC",
        "due": "pinned DESC, (due_date IS NULL), due_date ASC, id DESC",
        "receive": "pinned DESC, receive_time DESC, id DESC",
    }
    order = order_map.get(sort, order_map["recent"])

    total = conn.execute(f"SELECT COUNT(*) AS c FROM items{sql_where}", params).fetchone()["c"]
    page = max(int(filters.get("page") or 1), 1)
    page_size = min(max(int(filters.get("page_size") or 20), 1), 200)
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM items{sql_where} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_item(conn, r) for r in rows],
    }


def _validate_item_base(data: dict) -> None:
    if not (data.get("title") or "").strip():
        raise ValueError("事项标题不能为空")
    if not data.get("category"):
        raise ValueError("事项类别不能为空")
    if data["category"] not in CATEGORIES:
        raise ValueError(f"事项类别必须是：{'、'.join(CATEGORIES)}")
    if not data.get("source_type"):
        raise ValueError("来源类型不能为空")
    if data.get("due_type") not in (None, "clear", "convention", "none"):
        raise ValueError("时限性质不合法")


def create_item(conn: sqlite3.Connection, data: dict, op_source: str = "local") -> dict:
    _validate_item_base(data)
    receive_time = normalize_dt(data.get("receive_time"), now_str())
    due_type = data.get("due_type") or "clear"
    estimated_days = data.get("estimated_days")
    if estimated_days in (None, ""):
        defaults = get_setting(conn, "estimate_defaults", {}) or {}
        estimated_days = defaults.get(data["category"])
    if estimated_days is not None:
        estimated_days = float(estimated_days)
    due_date = day_str(data.get("due_date"))
    if not due_date and due_type == "clear" and estimated_days is not None:
        due_date = add_days(receive_time, estimated_days)
    if not due_date and due_type == "none":
        due_type = "none"

    item_no = next_item_no(conn, int(receive_time[:4]))
    created = now_str()
    attachments = data.get("attachments") or []
    cur = conn.execute(
        """
        INSERT INTO items(item_no, title, category, source_type, source_no, source_unit,
            receive_time, receive_method, due_date, original_due_date, due_type,
            estimated_days, status, handle_mode, current_handler, pinned, attachments,
            repeat_rule_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_no,
            data["title"].strip(),
            data["category"],
            data["source_type"],
            data.get("source_no"),
            data.get("source_unit"),
            receive_time,
            data.get("receive_method"),
            due_date,
            due_date,
            due_type,
            estimated_days,
            "pending",
            data.get("handle_mode") or "self",
            data.get("current_handler"),
            1 if data.get("pinned") else 0,
            dumps(attachments),
            data.get("repeat_rule_id"),
            created,
            created,
        ),
    )
    item_id = cur.lastrowid
    log_audit(conn, "item", item_id, "created", None, f"{item_no} {data['title']}", op_source=op_source)
    if due_date:
        log_audit(conn, "item", item_id, "due_date", None, due_date, op_source=op_source)
    return get_item_detail(conn, item_id)


def update_item(conn: sqlite3.Connection, item_id: int, payload: dict, op_source: str = "local") -> dict:
    old = dict(get_item_row(conn, item_id))
    if old.get("merged_into"):
        raise ValueError("该事项已合并至主事项，请在主事项上操作")
    new = dict(old)
    changed: list[str] = []

    for field in ITEM_EDITABLE_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field == "attachments":
            value = value or []
        elif field == "pinned":
            value = 1 if value else 0
        elif field == "delay_approved":
            value = None if value in (None, "") else (1 if value else 0)
        elif field in _DATE_FIELDS:
            value = day_str(value) if value else None
        elif field in ("receive_time", "finish_time"):
            value = normalize_dt(value) if value else None
        elif field in ("estimated_days", "actual_days"):
            value = float(value) if value not in (None, "") else None
        if new.get(field) != value:
            new[field] = value
            changed.append(field)

    if not changed:
        return get_item_detail(conn, item_id)

    if "status" in changed:
        old_status, new_status = old["status"], new["status"]
        if old_status == "finished" and new_status != "finished":
            raise ValueError("已办结事项需通过“重新打开”动作恢复办理，直接修改状态会破坏留痕")
        ensure_status_transition(old_status, new_status)
        if new_status == "finished":
            if not new.get("finish_method"):
                raise ValueError("办结必须填写办结方式")
            if not new.get("finish_time"):
                new["finish_time"] = now_str()
                changed.append("finish_time")
            new["actual_days"] = natural_days(new["receive_time"], new["finish_time"])
            if old.get("actual_days") != new["actual_days"]:
                changed.append("actual_days")
        elif new_status == "delayed":
            if not new.get("delay_reason"):
                raise ValueError("延期必须填写延期原因")
            if not new.get("delay_applied_to"):
                raise ValueError("延期必须填写向谁申请")

    if "delay_approved" in changed and new.get("delay_approved") == 1:
        if not new.get("delay_reason"):
            raise ValueError("批准延期前需先填写延期原因")
        if "due_date" not in changed:
            raise ValueError("批准延期需同时填写批准后的新时限")
        if not new.get("original_due_date"):
            new["original_due_date"] = old.get("due_date") or new.get("due_date")
            changed.append("original_due_date")
        if new.get("status") == "delayed":
            new["status"] = "in_process"
            changed.append("status")

    if "due_date" in changed and not new.get("original_due_date"):
        new["original_due_date"] = old.get("due_date")
        changed.append("original_due_date")

    if new.get("status") == "finished" and (
        "finish_time" in changed or "receive_time" in changed
    ):
        new["actual_days"] = natural_days(new["receive_time"], new.get("finish_time"))
        if "actual_days" not in changed:
            changed.append("actual_days")

    new["updated_at"] = now_str()
    set_clause = ", ".join(f"{f} = ?" for f in changed)
    values = []
    for f in changed:
        v = new[f]
        if f == "attachments":
            v = dumps(v)
        values.append(v)
    values.extend([new["updated_at"], item_id])
    conn.execute(f"UPDATE items SET {set_clause}, updated_at = ? WHERE id = ?", values)

    log_field_changes(conn, "item", item_id, old, new, changed, op_source=op_source)
    return get_item_detail(conn, item_id)


def finish_warnings(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT i.id, i.item_no, i.title, i.status
        FROM item_relations r JOIN items i ON i.id = r.related_item_id
        WHERE r.master_item_id = ? AND r.relation_type = 'parent_child'
          AND i.status != 'finished' AND i.merged_into IS NULL
        """,
        (item_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "item_no": r["item_no"],
            "title": r["title"],
            "message": f"子事项 {r['item_no']}「{r['title']}」尚未办结",
        }
        for r in rows
    ]


def create_record(conn: sqlite3.Connection, item_id: int, payload: dict, op_source: str = "local") -> dict:
    item = dict(get_item_row(conn, item_id))
    if item.get("merged_into"):
        raise ValueError("该事项已合并至主事项，请在主事项上补记过程")

    action = payload.get("action_type")
    if action not in _ACTION_VALUES:
        raise ValueError("无效的动作类型")
    content = (payload.get("content") or "").strip()

    for field in ACTION_REQUIRED_FIELDS.get(action, []):
        if field == "content":
            if not content:
                raise ValueError("请填写内容描述")
        elif not payload.get(field):
            raise ValueError(
                f"“{ACTION_LABEL.get(action, action)}”动作必须填写：{_field_label(field)}"
            )

    if action == "finish":
        if item["status"] == "finished":
            raise ValueError("该事项已办结，如需继续办理请先执行“重新打开”")
        content = content or payload.get("finish_summary") or "事项办结"
    if action == "delay":
        content = content or payload.get("delay_reason") or "申请延期"
    if action == "reopen" and item["status"] != "finished":
        raise ValueError("仅已办结事项可执行“重新打开”")

    action_time = normalize_dt(payload.get("action_time"), now_str())
    channels = payload.get("report_channels") or []
    attachments = payload.get("attachments") or []
    created = now_str()
    cur = conn.execute(
        """
        INSERT INTO process_records(item_id, action_type, action_time, report_channels,
            report_to, target_person, content, leader_opinion, attachments, origin_item_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            item_id,
            action,
            action_time,
            dumps(channels) if channels else None,
            payload.get("report_to"),
            payload.get("target_person"),
            content,
            payload.get("leader_opinion"),
            dumps(attachments) if attachments else None,
            created,
        ),
    )
    record_id = cur.lastrowid
    log_audit(conn, "process_record", record_id, "created", None, f"{ACTION_LABEL.get(action)}：{content}",
              op_source=op_source)

    new = dict(item)
    target = ACTION_TARGET_STATUS.get(action)
    if target:
        if target != item["status"]:
            ensure_status_transition(item["status"], target)
        new["status"] = target
        if action == "finish":
            new["finish_time"] = action_time
            new["finish_method"] = payload.get("finish_method") or item.get("finish_method")
            new["finish_summary"] = payload.get("finish_summary") or content
            new["actual_days"] = natural_days(item["receive_time"], action_time)
        elif action == "delay":
            new["delay_reason"] = payload.get("delay_reason")
            new["delay_applied_to"] = payload.get("delay_applied_to")
            new["delay_approved"] = 0
        elif action == "reopen":
            new["finish_time"] = None
            new["finish_method"] = None
            new["finish_summary"] = None
            new["actual_days"] = None
        elif action == "assign":
            new["handle_mode"] = "assigned"
            new["current_handler"] = payload.get("target_person")
    elif action in {"progress", "report", "instruction", "urge"} and item["status"] == "pending":
        new["status"] = "in_process"

    new["updated_at"] = now_str()
    changed = [f for f in ITEM_EDITABLE_FIELDS if old_val(item, f) != new.get(f)]
    if changed:
        set_clause = ", ".join(f"{f} = ?" for f in changed)
        values = [new[f] for f in changed] + [new["updated_at"], item_id]
        conn.execute(f"UPDATE items SET {set_clause}, updated_at = ? WHERE id = ?", values)
        log_field_changes(conn, "item", item_id, item, new, changed, op_source=op_source)

    warnings = finish_warnings(conn, item_id) if action == "finish" else []
    record = _record_dict(
        conn.execute(
            "SELECT pr.*, NULL AS origin_item_no FROM process_records pr WHERE pr.id = ?",
            (record_id,),
        ).fetchone()
    )
    return {
        "record": record,
        "item": get_item_detail(conn, item_id),
        "warnings": warnings,
    }


def old_val(item: dict, field: str):
    return item.get(field)


def _field_label(field: str) -> str:
    return {
        "finish_method": "办结方式",
        "delay_reason": "延期原因",
        "delay_applied_to": "向谁申请延期",
        "target_person": "交办对象",
        "content": "内容描述",
    }.get(field, field)


def set_pin(conn: sqlite3.Connection, item_id: int, pinned: bool) -> dict:
    old = dict(get_item_row(conn, item_id))
    value = 1 if pinned else 0
    if old.get("pinned") != value:
        conn.execute("UPDATE items SET pinned = ?, updated_at = ? WHERE id = ?", (value, now_str(), item_id))
        log_audit(conn, "item", item_id, "pinned", old.get("pinned"), value)
    return get_item_detail(conn, item_id)


def touch_view(conn: sqlite3.Connection, item_id: int) -> None:
    get_item_row(conn, item_id)
    conn.execute(
        "INSERT INTO item_views(item_id, viewed_at) VALUES (?, ?)"
        " ON CONFLICT(item_id) DO UPDATE SET viewed_at = excluded.viewed_at",
        (item_id, now_str()),
    )


def merge_items(
    conn: sqlite3.Connection, source_id: int, master_id: int, note: str | None = None
) -> dict:
    if source_id == master_id:
        raise ValueError("不能合并到自身")
    source = dict(get_item_row(conn, source_id))
    master = dict(get_item_row(conn, master_id))
    if source.get("merged_into"):
        raise ValueError("该事项已经合并过")
    if master.get("merged_into"):
        raise ValueError("目标事项已被合并，请选择主事项")

    now = now_str()
    conn.execute(
        "UPDATE items SET merged_into = ?, is_master = 0, updated_at = ? WHERE id = ?",
        (master_id, now, source_id),
    )
    conn.execute(
        "UPDATE process_records SET item_id = ?, origin_item_id = COALESCE(origin_item_id, ?)"
        " WHERE item_id = ?",
        (master_id, source_id, source_id),
    )
    master_attachments = loads(master.get("attachments"), []) or []
    for att in loads(source.get("attachments"), []) or []:
        master_attachments.append({**att, "origin_item_no": source.get("item_no")})
    conn.execute(
        "UPDATE items SET attachments = ?, updated_at = ? WHERE id = ?",
        (dumps(master_attachments), now, master_id),
    )
    existing = conn.execute(
        "SELECT id FROM item_relations WHERE master_item_id = ? AND related_item_id = ?"
        " AND relation_type = 'duplicate'",
        (master_id, source_id),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO item_relations(master_item_id, related_item_id, relation_type,"
            " created_time, created_method, note) VALUES (?, ?, 'duplicate', ?, 'manual', ?)",
            (master_id, source_id, now, note or "重复事项合并"),
        )
        conn.execute(
            "INSERT INTO audit_history(obj_type, obj_id, field_name, old_value, new_value,"
            " op_time, op_source) VALUES ('relation', last_insert_rowid(), 'created', NULL, ?, ?, 'local')",
            (f"重复合并 {source['item_no']} → {master['item_no']}", now),
        )
    log_audit(conn, "item", source_id, "merged_into", None, master["item_no"])
    log_audit(conn, "item", master_id, "merged_from", None, source["item_no"])
    return get_item_detail(conn, master_id)


def add_relation(conn: sqlite3.Connection, data: dict) -> dict:
    master_id = int(data.get("master_item_id") or 0)
    related_id = int(data.get("related_item_id") or 0)
    relation_type = data.get("relation_type")
    if relation_type not in _RELATION_VALUES:
        raise ValueError("关系类型必须是：相关 / 父子 / 重复")
    if master_id == related_id:
        raise ValueError("不能与自身建立关系")
    get_item_row(conn, master_id)
    get_item_row(conn, related_id)
    exists = conn.execute(
        "SELECT id FROM item_relations WHERE master_item_id = ? AND related_item_id = ?"
        " AND relation_type = ?",
        (master_id, related_id, relation_type),
    ).fetchone()
    if exists:
        raise ValueError("该关系已存在")
    created = now_str()
    cur = conn.execute(
        "INSERT INTO item_relations(master_item_id, related_item_id, relation_type,"
        " created_time, created_method, note) VALUES (?, ?, ?, ?, ?, ?)",
        (
            master_id,
            related_id,
            relation_type,
            created,
            data.get("created_method") or "manual",
            data.get("note"),
        ),
    )
    log_audit(conn, "relation", cur.lastrowid, "created", None,
              f"{RELATION_LABEL[relation_type]} {master_id}-{related_id}")
    return dict(conn.execute("SELECT * FROM item_relations WHERE id = ?", (cur.lastrowid,)).fetchone())


def delete_relation(conn: sqlite3.Connection, relation_id: int) -> None:
    row = conn.execute("SELECT * FROM item_relations WHERE id = ?", (relation_id,)).fetchone()
    if row is None:
        raise KeyError(f"关系 {relation_id} 不存在")
    conn.execute("DELETE FROM item_relations WHERE id = ?", (relation_id,))
    log_audit(conn, "relation", relation_id, "deleted", f"{row['master_item_id']}-{row['related_item_id']}", None)
