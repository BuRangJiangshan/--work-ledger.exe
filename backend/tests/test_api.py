"""后端核心业务规则测试。"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from io import BytesIO

from conftest import make_item


def test_meta_and_create_item(client):
    meta = client.get("/api/meta").json()
    assert "综治工单" in meta["categories"]
    assert meta["settings"]["close_remind_time"] == "17:30"

    item = make_item(client, title="XX社区邻里纠纷工单", source_no="GD-001",
                     source_unit="综治中心", receive_method="系统派单")
    assert item["item_no"].startswith("SX")
    assert item["status"] == "pending"
    assert item["due_date"] == "2026-11-27"
    assert item["original_due_date"] == "2026-11-27"
    assert item["remaining_days"] is not None

    listing = client.get("/api/items").json()
    assert listing["total"] == 1
    assert listing["items"][0]["title"] == "XX社区邻里纠纷工单"


def test_estimated_days_default_by_category(client):
    item = make_item(client, category="信访件", source_type="信访系统",
                     receive_time="2026-11-20T09:30", due_date=None, estimated_days=None)
    assert item["estimated_days"] == 60
    assert item["due_date"] == "2027-01-19"


def test_full_process_timeline_and_audit(client):
    item = make_item(client, title="一条完整事项")
    item_id = item["id"]

    def add(action, **extra):
        payload = {"action_type": action, "content": extra.pop("content", "内容")}
        payload.update(extra)
        resp = client.post(f"/api/items/{item_id}/records", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()

    add("progress", content="电话联系双方核实情况")
    add("report", content="电话向张主任汇报", report_to="张主任",
        report_channels=["电话"])
    add("instruction", content="批示", leader_opinion="先联合司法所调解")
    add("assign", content="转交王干事", target_person="王干事")
    result = add("urge", content="电话催办", target_person="王干事")
    assert result["item"]["status"] == "assigned"
    finish = add("finish", content="调解成功", finish_method="回单销号",
                 finish_summary="双方签订调解协议", action_time="2026-11-26T16:00")
    assert finish["item"]["status"] == "finished"
    assert finish["item"]["finish_method"] == "回单销号"
    assert finish["item"]["actual_days"] == 6

    detail = client.get(f"/api/items/{item_id}").json()
    assert len(detail["records"]) == 6
    actions = [r["action_type"] for r in detail["records"]]
    assert "report" in actions and "finish" in actions
    report_record = next(r for r in detail["records"] if r["action_type"] == "report")
    assert report_record["report_channels"] == ["电话"]
    assert detail["audit"], "审计历史不应为空"
    assert any(a["field_name"] == "status" for a in detail["audit"])


def test_status_transition_guards(client):
    item = make_item(client, title="状态流转")
    item_id = item["id"]

    resp = client.patch(f"/api/items/{item_id}", json={"status": "finished"})
    assert resp.status_code == 400  # 缺少办结方式

    resp = client.patch(f"/api/items/{item_id}",
                        json={"status": "finished", "finish_method": "回单销号"})
    assert resp.status_code == 200, resp.text

    resp = client.patch(f"/api/items/{item_id}", json={"status": "assigned"})
    assert resp.status_code == 400
    assert "重新打开" in resp.json()["detail"]

    resp = client.post(f"/api/items/{item_id}/records",
                       json={"action_type": "reopen", "content": ""})
    assert resp.status_code == 400

    resp = client.post(f"/api/items/{item_id}/records",
                       json={"action_type": "reopen", "content": "上级要求继续办理"})
    assert resp.status_code == 200, resp.text
    detail = resp.json()["item"]
    assert detail["status"] == "in_process"
    assert detail["finish_time"] is None
    assert detail["actual_days"] is None


def test_delay_requires_reason_and_approval(client):
    item = make_item(client, title="延期事项")
    item_id = item["id"]

    resp = client.post(f"/api/items/{item_id}/records",
                       json={"action_type": "delay", "content": "需延期"})
    assert resp.status_code == 400

    resp = client.post(f"/api/items/{item_id}/records",
                       json={"action_type": "delay", "content": "需延期",
                             "delay_reason": "双方外出", "delay_applied_to": "张主任"})
    assert resp.status_code == 200
    assert resp.json()["item"]["status"] == "delayed"

    detail = client.get(f"/api/items/{item_id}").json()
    assert detail["original_due_date"] == "2026-11-27"
    assert detail["delay_approved"] == 0

    resp = client.patch(f"/api/items/{item_id}", json={"delay_approved": 1})
    assert resp.status_code == 400  # 未给新时限

    resp = client.patch(f"/api/items/{item_id}",
                        json={"delay_approved": 1, "due_date": "2026-12-10"})
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["due_date"] == "2026-12-10"
    assert detail["original_due_date"] == "2026-11-27"
    assert detail["status"] == "in_process"


def test_parent_child_finish_warning(client):
    parent = make_item(client, title="专项整治")
    child = make_item(client, title="专项整治-子事项")
    resp = client.post("/api/relations", json={
        "master_item_id": parent["id"], "related_item_id": child["id"],
        "relation_type": "parent_child", "note": "拆分",
    })
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/api/items/{parent['id']}/records", json={
        "action_type": "finish", "content": "办结", "finish_method": "归档",
    })
    assert resp.status_code == 200
    warnings = resp.json()["warnings"]
    assert len(warnings) == 1
    assert child["item_no"] in warnings[0]["message"]

    detail = client.get(f"/api/items/{parent['id']}").json()
    assert len(detail["relations"]) == 1
    assert detail["relations"][0]["relation_label"] == "父子"


def test_merge_keeps_trace_and_dedupes_stats(client):
    master = make_item(client, title="同一诉求-主件", category="信访件",
                       source_type="信访系统")
    source = make_item(client, title="同一诉求-重复件", category="群众投诉",
                       source_type="群众来电")
    other = make_item(client, title="另一件事", category="日常事务",
                      source_type="其他")

    client.post(f"/api/items/{source['id']}/records",
                json={"action_type": "progress", "content": "重复来源受理"})

    resp = client.post(f"/api/items/{source['id']}/merge",
                       json={"master_id": master["id"], "note": "同一诉求"})
    assert resp.status_code == 200, resp.text
    merged_master = resp.json()
    assert len(merged_master["merged_sources"]) == 1
    assert merged_master["merged_sources"][0]["item_no"] == source["item_no"]
    assert len(merged_master["records"]) == 1
    assert merged_master["records"][0]["origin_item_no"] == source["item_no"]

    source_detail = client.get(f"/api/items/{source['id']}").json()
    assert source_detail["merged_into"] == master["id"]
    assert source_detail["merged_into_item"]["item_no"] == master["item_no"]

    listing = client.get("/api/items").json()
    assert listing["total"] == 2
    all_items = client.get("/api/items", params={"include_merged": True}).json()
    assert all_items["total"] == 3

    stats = client.get("/api/stats").json()
    assert stats["total_received"] == 2
    assert stats["by_source"][0]["name"] in ("信访系统", "其他")


def test_merge_validation(client):
    a = make_item(client, title="A")
    b = make_item(client, title="B")
    assert client.post(f"/api/items/{a['id']}/merge", json={"master_id": a["id"]}).status_code == 400
    assert client.post(f"/api/items/{a['id']}/merge", json={"master_id": b["id"]}).status_code == 200
    assert client.post(f"/api/items/{b['id']}/merge", json={"master_id": a["id"]}).status_code == 400


def test_audit_is_append_only(client):
    from app.db import get_conn

    item = make_item(client, title="审计保护")
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM audit_history LIMIT 1").fetchone()
        assert row is not None
        try:
            conn.execute("UPDATE audit_history SET field_name = 'x' WHERE id = ?", (row["id"],))
            conn.commit()
            raise AssertionError("审计表不允许更新")
        except sqlite3.DatabaseError:
            conn.rollback()
        try:
            conn.execute("DELETE FROM audit_history WHERE id = ?", (row["id"],))
            conn.commit()
            raise AssertionError("审计表不允许删除")
        except sqlite3.DatabaseError:
            conn.rollback()
    finally:
        conn.close()


def test_saved_filters_and_settings(client):
    resp = client.post("/api/filters", json={
        "name": "本周信访件",
        "filter_json": {"category": "信访件", "receive_from": "2026-11-16"},
    })
    assert resp.status_code == 200
    filters = client.get("/api/filters").json()
    assert len(filters) == 1
    assert filters[0]["filter_json"]["category"] == "信访件"

    resp = client.put("/api/settings", json={"close_remind_time": "18:00",
                                             "estimate_defaults": {"信访件": 45}})
    assert resp.status_code == 200
    assert resp.json()["close_remind_time"] == "18:00"
    assert client.get("/api/meta").json()["settings"]["close_remind_time"] == "18:00"


def test_dashboard_buckets_and_recent(client):
    today = date.today()
    overdue = make_item(client, title="超期事项",
                        receive_time=(today - timedelta(days=10)).isoformat() + "T09:00",
                        due_date=(today - timedelta(days=2)).isoformat())
    due_today = make_item(client, title="今日到期", due_date=today.isoformat())
    make_item(client, title="三天内", due_date=(today + timedelta(days=2)).isoformat())
    make_item(client, title="充裕", due_date=(today + timedelta(days=20)).isoformat())

    client.get(f"/api/items/{overdue['id']}")
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["counts"]["overdue"] == 1
    assert any(i["id"] == overdue["id"] for i in dashboard["red"])
    assert any(i["id"] == due_today["id"] for i in dashboard["red"])
    assert len(dashboard["yellow"]) == 1
    assert dashboard["recent"] and dashboard["recent"][0]["id"] == overdue["id"]


def test_daily_close_unique(client):
    today = date.today().isoformat()
    resp = client.post("/api/daily-close",
                       json={"date": today, "status": "done"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "done"

    resp = client.post("/api/daily-close",
                       json={"date": today, "status": "done"})
    assert resp.status_code == 409

    resp = client.post("/api/daily-close",
                       json={"date": "2026-11-22", "status": "skipped",
                             "skip_reason": "外出开会"})
    assert resp.status_code == 200
    assert resp.json()["skip_reason"] == "外出开会"

    summary = client.get("/api/daily-close", params={"date": today}).json()
    assert summary["log"]["status"] == "done"
    assert summary["log"]["summary_snapshot"]["counts"] is not None


def test_stats_three_bucket_classification(client):
    # 按期办结
    a = make_item(client, title="按期办结", receive_time="2026-11-01T09:00",
                  due_date="2026-11-10")
    client.patch(f"/api/items/{a['id']}", json={
        "status": "finished", "finish_method": "回单销号", "finish_time": "2026-11-09T10:00",
    })
    # 批准延期办结
    b = make_item(client, title="批准延期办结", receive_time="2026-11-01T09:00",
                  due_date="2026-11-10")
    client.patch(f"/api/items/{b['id']}", json={
        "delay_reason": "双方外出", "delay_applied_to": "张主任",
        "delay_approved": 1, "due_date": "2026-11-20",
    })
    client.patch(f"/api/items/{b['id']}", json={
        "status": "finished", "finish_method": "书面答复", "finish_time": "2026-11-18T10:00",
    })
    # 超期办结
    c = make_item(client, title="超期办结", receive_time="2026-11-01T09:00",
                  due_date="2026-11-10")
    client.patch(f"/api/items/{c['id']}", json={
        "status": "finished", "finish_method": "归档", "finish_time": "2026-11-15T10:00",
    })
    # 无明确时限
    d = make_item(client, title="无时限办结", receive_time="2026-11-02T09:00",
                  due_type="none", due_date=None)
    client.patch(f"/api/items/{d['id']}", json={
        "status": "finished", "finish_method": "归档", "finish_time": "2026-11-06T10:00",
    })

    stats = client.get("/api/stats", params={"start": "2026-11-01", "end": "2026-11-30"}).json()
    assert stats["total_received"] == 4
    assert stats["on_time"] == 1
    assert stats["approved_delay"] == 1
    assert stats["overdue"] == 1
    assert stats["no_due"] == 1
    assert stats["denominator"] == 3
    assert stats["finish_rate"] == 33.3
    assert stats["by_category"]
    assert stats["monthly"][0]["month"] == "2026-11"


def test_report_preview_and_docx(client):
    a = make_item(client, title="信访事项A", category="信访件",
                  source_type="信访系统", source_no="XF-01")
    client.patch(f"/api/items/{a['id']}", json={
        "status": "finished", "finish_method": "书面答复",
        "finish_summary": "已答复当事人", "finish_time": "2026-11-21T10:00",
    })
    make_item(client, title="综治工单B", category="综治工单")

    templates = client.get("/api/report-templates").json()
    assert any(t["source"] == "builtin" for t in templates)
    builtin = next(t for t in templates if t["source"] == "builtin")

    report = client.post("/api/reports/preview", json={
        "template_id": builtin["id"], "start": "2026-11-01", "end": "2026-11-30",
        "organize": "category",
    }).json()
    assert report["item_count"] == 2
    text = report["text"]
    assert "一、上级交办及部署工作进展情况" in text
    assert "信访事项A" in text and "综治工单B" in text
    assert "按期办结" in text

    status_report = client.post("/api/reports/preview", json={
        "template_id": builtin["id"], "start": "2026-11-01", "end": "2026-11-30",
        "organize": "status",
    }).json()
    assert status_report["sections"][0]["heading"] == "一、已完成事项"

    resp = client.post("/api/reports/export", json={
        "template_id": builtin["id"], "start": "2026-11-01", "end": "2026-11-30",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 1000


def test_item_report_and_export(client):
    item = make_item(client, title="单件报告事项")
    client.post(f"/api/items/{item['id']}/records",
                json={"action_type": "report", "content": "电话汇报", "report_to": "张主任"})
    preview = client.get(f"/api/reports/items/{item['id']}/preview").json()
    assert "办理情况报告" in preview["title"]
    assert any("办理过程" in s["heading"] for s in preview["sections"])
    resp = client.get(f"/api/reports/items/{item['id']}/export")
    assert resp.status_code == 200
    assert len(resp.content) > 1000


def test_template_import_docx(client):
    from docx import Document

    doc = Document()
    doc.add_heading("一、重点工作进展", level=1)
    doc.add_paragraph("示例正文")
    doc.add_heading("二、其他事项", level=1)
    buf = BytesIO()
    doc.save(buf)
    resp = client.post(
        "/api/report-templates/import",
        files={"file": ("单位周报样例.docx", buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"name": "单位周报模板"},
    )
    assert resp.status_code == 200, resp.text
    template = resp.json()
    assert template["source"] == "imported"
    assert "一、重点工作进展" in template["structure"]["headings"]


def test_repeat_rule_generates_item(client):
    resp = client.post("/api/repeats", json={
        "name": "每周一上传周报台账",
        "item_template": {"title": "上传周报台账 {date}", "category": "日常事务",
                          "source_type": "其他"},
        "trigger_type": "fixed",
        "schedule": {"freq": "weekly", "weekday": 0, "time": "09:00"},
        "backlog_strategy": "keep_all",
    })
    assert resp.status_code == 200, resp.text

    from app.db import get_conn
    conn = get_conn()
    try:
        conn.execute("UPDATE repeat_rules SET next_run_time = '2026-01-05T09:00'")
        conn.commit()
    finally:
        conn.close()

    resp = client.post("/api/repeats/process")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1

    listing = client.get("/api/items", params={"q": "上传周报台账"}).json()
    assert listing["total"] >= 1


def test_export_and_backup(client):
    make_item(client, title="导出测试")
    resp = client.get("/api/export/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tables"]["items"][0]["title"] == "导出测试"

    resp = client.get("/api/export/csv")
    assert resp.status_code == 200
    assert "事项编号" in resp.content.decode("utf-8-sig")

    resp = client.get("/api/export/xlsx")
    assert resp.status_code == 200
    assert len(resp.content) > 1000

    resp = client.post("/api/backup")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_attachment_upload(client):
    resp = client.post("/api/attachments",
                       files={"file": ("调解协议.txt", b"hello", "text/plain")})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "调解协议.txt"
    filed = client.get(data["url"])
    assert filed.status_code == 200
    assert filed.content == b"hello"


def test_global_timeline_filter(client):
    item = make_item(client, title="时间线事项")
    client.post(f"/api/items/{item['id']}/records",
                json={"action_type": "report", "content": "汇报"})
    client.post(f"/api/items/{item['id']}/records",
                json={"action_type": "urge", "content": "催办"})
    rows = client.get("/api/timeline").json()
    assert len(rows) == 2
    only_report = client.get("/api/timeline", params={"types": "report"}).json()
    assert len(only_report) == 1
    assert only_report[0]["action_label"] == "向领导汇报"
    assert only_report[0]["item_title"] == "时间线事项"
