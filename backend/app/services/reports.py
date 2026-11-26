"""汇报生成（预览文本 + Word 导出）与模板导入。"""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date
from io import BytesIO

from ..config import UPLOAD_DIR
from ..status import (
    ACTION_LABEL,
    BUILTIN_TEMPLATE_NAME,
    BUILTIN_TEMPLATE_STRUCTURE,
    CATEGORIES,
    REPORT_GROUPS,
    RELATION_LABEL,
    STATUS_LABEL,
    status_label,
)
from ..utils import dumps, loads, natural_days, now_str, parse_date, today_str
from .items import get_item_detail, serialize_item
from .settings import get_setting
from .stats import classify_finish


def list_templates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM report_templates ORDER BY id").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["structure"] = loads(d.get("structure"), {}) or {}
        d["builtin"] = d["source"] == "builtin"
        result.append(d)
    return result


def create_custom_template(conn: sqlite3.Connection, name: str, headings: list[str]) -> dict:
    name = (name or "").strip()
    headings = [h.strip() for h in (headings or []) if h and h.strip()]
    if not name:
        raise ValueError("模板名称不能为空")
    if not headings:
        raise ValueError("模板至少需要一个分类标题")
    structure = {"type": "custom", "headings": headings}
    cur = conn.execute(
        "INSERT INTO report_templates(name, source, file_path, structure, created_at)"
        " VALUES (?, 'custom', NULL, ?, ?)",
        (name, dumps(structure), now_str()),
    )
    row = conn.execute("SELECT * FROM report_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
    d = dict(row)
    d["structure"] = structure
    return d


def delete_template(conn: sqlite3.Connection, template_id: int) -> None:
    row = conn.execute("SELECT * FROM report_templates WHERE id = ?", (template_id,)).fetchone()
    if row is None:
        raise KeyError(f"模板 {template_id} 不存在")
    if row["source"] == "builtin":
        raise ValueError("内置模板不能删除")
    conn.execute("DELETE FROM report_templates WHERE id = ?", (template_id,))


def import_template(
    conn: sqlite3.Connection, filename: str, content: bytes, name: str | None = None
) -> dict:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    headings: list[str] = []
    columns: list[str] = []
    if suffix == "docx":
        from docx import Document

        doc = Document(BytesIO(content))
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name or "").lower()
            if (
                style.startswith("heading")
                or re.match(r"^[一二三四五六七八九十]+[、.．]", text)
                or re.match(r"^\d+[、.．]", text)
            ):
                headings.append(text)
        if not headings:
            headings = [
                p.text.strip()
                for p in doc.paragraphs
                if p.text.strip() and len(p.text.strip()) <= 40
            ][:8]
        if doc.tables:
            columns = [c.text.strip() for c in doc.tables[0].rows[0].cells if c.text.strip()]
    elif suffix in ("xlsx", "xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(BytesIO(content), data_only=True)
        headings = wb.sheetnames
        ws = wb[wb.sheetnames[0]]
        columns = [
            str(c.value).strip()
            for c in next(ws.iter_rows(min_row=1, max_row=1))
            if c.value is not None
        ]
    else:
        raise ValueError("仅支持 Word（.docx）或 Excel（.xlsx）样例文件")
    if not headings:
        headings = ["一、工作进展情况", "二、其他事项"]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
    stored.write_bytes(content)
    structure = {"type": "imported", "headings": headings, "columns": columns}
    template_name = (name or "").strip() or filename.rsplit(".", 1)[0]
    cur = conn.execute(
        "INSERT INTO report_templates(name, source, file_path, structure, created_at)"
        " VALUES (?, 'imported', ?, ?, ?)",
        (template_name, str(stored), dumps(structure), now_str()),
    )
    row = conn.execute("SELECT * FROM report_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
    d = dict(row)
    d["structure"] = structure
    return d


def _fetch_items(conn: sqlite3.Connection, start: str | None, end: str | None) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM items WHERE merged_into IS NULL ORDER BY receive_time ASC"
    ).fetchall()
    items = [dict(r) for r in rows]
    if not start and not end:
        return items
    start_dt = (start or "0000-01-01") + "T00:00"
    end_dt = (end or "9999-12-31") + "T23:59"
    result = []
    for item in items:
        records = conn.execute(
            "SELECT 1 FROM process_records WHERE item_id = ? AND action_time BETWEEN ? AND ? LIMIT 1",
            (item["id"], start_dt, end_dt),
        ).fetchone()
        if (
            (start_dt <= item["receive_time"] <= end_dt)
            or (item.get("finish_time") and start_dt <= item["finish_time"] <= end_dt)
            or records
        ):
            result.append(item)
    return result


def _latest_record(conn: sqlite3.Connection, item_id: int, action_types: tuple[str, ...]):
    placeholders = ",".join("?" for _ in action_types)
    return conn.execute(
        f"SELECT * FROM process_records WHERE item_id = ? AND action_type IN ({placeholders})"
        " ORDER BY action_time DESC, id DESC LIMIT 1",
        (item_id, *action_types),
    ).fetchone()


def _finish_text(item: dict) -> str:
    cls = classify_finish(item)
    if cls == "approved_delay":
        reason = item.get("delay_reason") or "未填写"
        return f"经批准延期并在新时限内办结（延期原因：{reason}；申请对象：{item.get('delay_applied_to') or '—'}）"
    if cls == "on_time":
        return "按期办结"
    if cls == "overdue":
        return "超期办结"
    return "已办结（无明确时限）"


def _item_line(conn: sqlite3.Connection, item: dict, index: int) -> str:
    meta = [f"来源：{item['source_type']}"]
    if item.get("source_unit"):
        meta.append(f"来文单位：{item['source_unit']}")
    if item.get("source_no"):
        meta.append(f"编号：{item['source_no']}")
    meta.append(f"接收时间 {item['receive_time'][:10]}")
    if item.get("receive_method"):
        meta.append(f"接收方式：{item['receive_method']}")
    line = f"{index}. {item['title']}（{'；'.join(meta)}）"

    if item["status"] == "finished" and item.get("finish_time"):
        days = item.get("actual_days")
        if days is None:
            days = natural_days(item["receive_time"], item["finish_time"])
        line += f"——已于 {item['finish_time'][:10]} 办结，用时 {int(days or 0)} 个自然日，{_finish_text(item)}"
        if item.get("finish_summary"):
            line += f"；办理结果：{item['finish_summary'].rstrip('。')}"
        line += "。"
    else:
        parts = [f"当前{status_label(item['status'])}"]
        if item.get("current_handler"):
            parts.append(f"承办人：{item['current_handler']}")
        if item.get("due_date"):
            parts.append(f"要求 {item['due_date'][:10]} 前办结")
            due = parse_date(item["due_date"])
            if due:
                remaining = (due - date.today()).days
                parts.append(f"剩余 {remaining} 天" if remaining >= 0 else f"已超期 {abs(remaining)} 天")
        else:
            parts.append("无明确时限")
        line += "——" + "，".join(parts)
        latest = _latest_record(conn, item["id"], ("progress", "feedback", "urge"))
        if latest and latest["content"]:
            line += f"；最新进展：{latest['content'].rstrip('。')}"
        line += "。"

    instruction = _latest_record(conn, item["id"], ("instruction",))
    if instruction and (instruction["leader_opinion"] or instruction["content"]):
        line += f"领导批示：{(instruction['leader_opinion'] or instruction['content']).rstrip('。')}。"

    merged = item.get("merged_sources") or []
    if merged:
        nos = "、".join(m["item_no"] or "" for m in merged)
        line += f"（同一事项多来源合并，已合并：{nos}）"
    return line


def _groups_from_structure(structure: dict) -> list[tuple[str, list[str]]]:
    groups = structure.get("groups") or []
    if groups:
        return [(g["heading"], g.get("categories") or []) for g in groups]
    headings = structure.get("headings") or []
    result: list[tuple[str, list[str]]] = []
    for heading in headings:
        cats = [c for c in CATEGORIES if c in heading]
        if not cats:
            if any(k in heading for k in ("上级", "领导", "部署")):
                cats = ["上级交办", "会议部署"]
            elif any(k in heading for k in ("信访", "群众", "诉求")):
                cats = ["信访件", "群众投诉"]
            elif any(k in heading for k in ("综治", "工单")):
                cats = ["综治工单"]
        result.append((heading, cats))
    return result


def _category_sections(conn: sqlite3.Connection, items: list[dict], structure: dict):
    groups = _groups_from_structure(structure) or list(REPORT_GROUPS)
    used: set[int] = set()
    sections: list[dict] = []
    generic_index: int | None = None
    for heading, cats in groups:
        section = {"heading": heading, "lines": [], "items": []}
        if cats:
            section["items"] = [i for i in items if i["category"] in cats]
            used.update(i["id"] for i in section["items"])
        elif generic_index is None:
            generic_index = len(sections)
        sections.append(section)
    leftovers = [i for i in items if i["id"] not in used]
    if leftovers:
        if generic_index is not None:
            sections[generic_index]["items"].extend(leftovers)
        else:
            sections.append({"heading": "其他事项", "lines": [], "items": leftovers})
    for section in sections:
        section["lines"] = [
            _item_line(conn, item, idx)
            for idx, item in enumerate(section["items"], start=1)
        ]
    return sections


def build_report(
    conn: sqlite3.Connection,
    template_id: int | None,
    start: str | None,
    end: str | None,
    organize: str = "category",
) -> dict:
    template = None
    if template_id:
        row = conn.execute("SELECT * FROM report_templates WHERE id = ?", (template_id,)).fetchone()
        if row is None:
            raise KeyError(f"模板 {template_id} 不存在")
        template = dict(row)
    if template is None:
        row = conn.execute(
            "SELECT * FROM report_templates WHERE source = 'builtin' ORDER BY id LIMIT 1"
        ).fetchone()
        template = dict(row) if row else {"name": BUILTIN_TEMPLATE_NAME, "structure": dumps(BUILTIN_TEMPLATE_STRUCTURE)}

    structure = loads(template.get("structure"), {}) or BUILTIN_TEMPLATE_STRUCTURE
    items = _fetch_items(conn, start, end)
    finished = [i for i in items if i["status"] == "finished"]

    if organize == "status":
        sections = [
            {
                "heading": "一、已完成事项",
                "items": [i for i in items if i["status"] == "finished"],
                "lines": [],
            },
            {
                "heading": "二、进行中事项",
                "items": [
                    i
                    for i in items
                    if i["status"] in ("in_process", "assigned", "review", "delayed", "suspended")
                ],
                "lines": [],
            },
            {
                "heading": "三、待办事项",
                "items": [i for i in items if i["status"] == "pending"],
                "lines": [],
            },
        ]
        for section in sections:
            section["lines"] = [
                _item_line(conn, item, idx)
                for idx, item in enumerate(section["items"], start=1)
            ]
    else:
        sections = _category_sections(conn, items, structure)

    unit = get_setting(conn, "unit_name", "") or ""
    range_text = (
        f"{start} 至 {end}"
        if start and end
        else (start or end or "全部")
    )
    title = f"{unit}工作汇报" if unit else "工作汇报"
    subtitle = f"（{range_text}）"
    summary_line = f"本期共涉及事项 {len(items)} 件，其中已办结 {len(finished)} 件。"
    text_lines = [title, subtitle, "", summary_line, ""]
    for section in sections:
        text_lines.append(section["heading"])
        text_lines.extend(section["lines"])
        text_lines.append("")
    if not sections:
        text_lines.append("本期间无相关事项。")

    return {
        "title": title,
        "subtitle": subtitle,
        "template_name": template.get("name"),
        "start": start,
        "end": end,
        "organize": organize,
        "sections": sections,
        "item_count": len(items),
        "finished_count": len(finished),
        "summary_line": summary_line,
        "text": "\n".join(text_lines),
    }


def build_item_report(conn: sqlite3.Connection, item_id: int) -> dict:
    detail = get_item_detail(conn, item_id)
    sections = []
    base = []
    base.append(f"事项类别：{detail['category']}；来源：{detail['source_type']}"
                + (f"（{detail['source_unit']}）" if detail.get("source_unit") else ""))
    base.append(f"接收时间：{detail['receive_time'].replace('T', ' ')}；接收方式：{detail.get('receive_method') or '—'}")
    if detail.get("due_date"):
        base.append(f"要求办结时间：{detail['due_date']}；时限性质：{detail.get('due_type')}")
    base.append(f"当前状态：{STATUS_LABEL.get(detail['status'], detail['status'])}"
                + (f"；承办人：{detail['current_handler']}" if detail.get("current_handler") else ""))
    sections.append({"heading": "一、基本情况", "lines": base})

    process_lines = []
    for record in reversed(detail["records"]):
        when = record["action_time"].replace("T", " ")[5:16]
        line = f"{when} {ACTION_LABEL.get(record['action_type'], record['action_type'])}：{record['content']}"
        extra = []
        if record.get("report_to"):
            extra.append(f"汇报对象：{record['report_to']}")
        if record.get("target_person"):
            extra.append(f"对象：{record['target_person']}")
        if record.get("report_channels"):
            extra.append(f"渠道：{'、'.join(record['report_channels'])}")
        if record.get("origin_item_no"):
            extra.append(f"原事项编号：{record['origin_item_no']}")
        if extra:
            line += f"（{'；'.join(extra)}）"
        if record.get("leader_opinion"):
            line += f"；领导批示：{record['leader_opinion']}"
        process_lines.append(line)
    sections.append({"heading": "二、办理过程", "lines": process_lines or ["暂无过程记录。"]})

    result_lines = []
    if detail["status"] == "finished":
        days = detail.get("actual_days")
        result_lines.append(
            f"办结时间：{detail['finish_time'].replace('T', ' ')}；办结方式：{detail.get('finish_method') or '—'}；"
            f"实际用时：{int(days or 0)} 个自然日；{_finish_text(detail)}。"
        )
        if detail.get("finish_summary"):
            result_lines.append(f"结果摘要：{detail['finish_summary']}")
    else:
        result_lines.append(
            f"当前处于“{STATUS_LABEL.get(detail['status'], detail['status'])}”状态"
            + (f"，要求 {detail['due_date']} 前办结" if detail.get("due_date") else "，无明确时限")
            + "。"
        )
        latest = _latest_record(conn, item_id, ("progress", "feedback", "urge"))
        if latest:
            result_lines.append(f"最新进展：{latest['content']}")
    sections.append({"heading": "三、办理结果", "lines": result_lines})

    relation_lines = []
    for relation in detail.get("relations") or []:
        relation_lines.append(
            f"{RELATION_LABEL.get(relation['relation_type'], relation['relation_type'])}关系："
            f"{relation['other']['item_no']} {relation['other']['title']}（{relation['direction']}方向）"
        )
    if detail.get("merged_sources"):
        relation_lines.append(
            "已合并重复事项：" + "、".join(m["item_no"] for m in detail["merged_sources"])
        )
    if relation_lines:
        sections.append({"heading": "四、关联事项", "lines": relation_lines})

    title = f"{detail['item_no']} {detail['title']} 办理情况报告"
    subtitle = f"（生成日期：{today_str()}）"
    text = "\n".join(
        [title, subtitle, ""] + [f"{s['heading']}\n" + "\n".join(s["lines"]) for s in sections]
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "sections": sections,
        "text": text,
        "item": detail,
    }


def _set_run_font(run, name: str, size: float | None = None, bold: bool = False) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt

    run.font.name = name
    if size:
        run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:eastAsia"), name)


def render_docx(report: dict, path) -> str:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(title_p.add_run(report["title"]), "黑体", 22, True)
    if report.get("subtitle"):
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_run_font(sub_p.add_run(report["subtitle"]), "仿宋", 12)

    for section in report["sections"]:
        heading_p = doc.add_paragraph()
        heading_p.paragraph_format.space_before = Pt(12)
        _set_run_font(heading_p.add_run(section["heading"]), "黑体", 15, True)
        lines = section.get("lines") or []
        if not lines:
            lines = ["本项无事项。"]
        for line in lines:
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Pt(24)
            p.paragraph_format.line_spacing = 1.5
            _set_run_font(p.add_run(line), "仿宋", 12)
    doc.save(path)
    return path
