"""状态机与业务字典（前后端共用的唯一来源，通过 /api/meta 下发）。"""
from __future__ import annotations

STATUSES = [
    {"value": "pending", "label": "待处理", "color": "info"},
    {"value": "in_process", "label": "办理中", "color": "primary"},
    {"value": "review", "label": "待领导审定", "color": "warning"},
    {"value": "assigned", "label": "已交办", "color": "primary"},
    {"value": "finished", "label": "已办结", "color": "success"},
    {"value": "delayed", "label": "延期", "color": "danger"},
    {"value": "suspended", "label": "挂起", "color": "info"},
]
STATUS_LABEL = {s["value"]: s["label"] for s in STATUSES}

CATEGORIES = ["综治工单", "信访件", "群众投诉", "上级交办", "会议部署", "日常事务", "其他"]

SOURCE_TYPES = [
    "综治信息系统", "信访系统", "群众来电", "群众来访",
    "上级交办", "领导交办", "会议部署", "其他",
]

RECEIVE_METHODS = ["系统派单", "文件", "电话", "口头", "微信/QQ转达"]

DUE_TYPES = [
    {"value": "clear", "label": "明确期限"},
    {"value": "convention", "label": "惯例期限"},
    {"value": "none", "label": "无明确期限"},
]
DUE_TYPE_LABEL = {d["value"]: d["label"] for d in DUE_TYPES}

REPORT_CHANNELS = ["书面", "口头", "电话", "微信", "QQ", "其他"]

FINISH_METHODS = ["回单销号", "书面答复", "口头答复", "归档"]

HANDLE_MODES = [
    {"value": "self", "label": "本人办理"},
    {"value": "assigned", "label": "交办他人"},
]

RELATION_TYPES = [
    {"value": "related", "label": "相关"},
    {"value": "parent_child", "label": "父子"},
    {"value": "duplicate", "label": "重复"},
]
RELATION_LABEL = {r["value"]: r["label"] for r in RELATION_TYPES}

ACTION_TYPES = [
    {"value": "progress", "label": "处理进展"},
    {"value": "report", "label": "向领导汇报"},
    {"value": "instruction", "label": "领导批示"},
    {"value": "assign", "label": "交办"},
    {"value": "urge", "label": "催办"},
    {"value": "feedback", "label": "接收反馈"},
    {"value": "finish", "label": "办结"},
    {"value": "delay", "label": "延期"},
    {"value": "reopen", "label": "重新打开"},
]
ACTION_LABEL = {a["value"]: a["label"] for a in ACTION_TYPES}

# 允许的状态流转
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_process", "review", "assigned", "delayed", "suspended", "finished"},
    "in_process": {"review", "assigned", "delayed", "suspended", "finished"},
    "review": {"in_process", "assigned", "delayed", "finished"},
    "assigned": {"in_process", "review", "delayed", "suspended", "finished"},
    "delayed": {"in_process", "suspended", "finished"},
    "suspended": {"in_process", "delayed", "finished"},
    "finished": {"in_process"},  # 仅允许"重新打开"
}

# 动作触发的目标状态
ACTION_TARGET_STATUS = {
    "finish": "finished",
    "delay": "delayed",
    "reopen": "in_process",
    "assign": "assigned",
}

# 动作触发的必填字段
ACTION_REQUIRED_FIELDS = {
    "finish": ["finish_method"],
    "delay": ["delay_reason", "delay_applied_to"],
    "reopen": ["content"],
    "assign": ["target_person"],
}

REPORT_ACTIONS = {"report"}

# 汇报模板分类分组（内置通用模板使用）
REPORT_GROUPS = [
    ("一、上级交办及部署工作进展情况", ["上级交办", "会议部署"]),
    ("二、信访件及群众诉求办理情况", ["信访件", "群众投诉"]),
    ("三、综治工单办理情况", ["综治工单"]),
    ("四、其他事项", ["日常事务", "其他"]),
]

DEFAULT_SETTINGS = {
    "close_remind_time": "17:30",
    "estimate_defaults": {
        "信访件": 60,
        "综治工单": 9,
        "群众投诉": 7,
        "上级交办": 7,
        "会议部署": 3,
        "日常事务": 1,
        "其他": 3,
    },
    "urge_rules": {"remaining_days": [3, 1, 0], "overdue_daily": True},
    "unit_name": "",
    "close_enabled": True,
}

BUILTIN_TEMPLATE_NAME = "通用公文汇报模板（内置）"
BUILTIN_TEMPLATE_STRUCTURE = {
    "type": "builtin",
    "headings": [h for h, _ in REPORT_GROUPS],
    "groups": [{"heading": h, "categories": c} for h, c in REPORT_GROUPS],
}


def ensure_status_transition(old: str, new: str) -> None:
    """校验状态流转，非法时抛出 ValueError。"""
    if not new or old == new:
        return
    allowed = ALLOWED_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise ValueError(
            f"状态不能从“{STATUS_LABEL.get(old, old)}”直接变更为“{STATUS_LABEL.get(new, new)}”"
        )


def status_label(value: str | None) -> str:
    return STATUS_LABEL.get(value or "", value or "")


def action_label(value: str | None) -> str:
    return ACTION_LABEL.get(value or "", value or "")
