# 事项办理全程留痕工具

一个 **本地运行、无云依赖、全程留痕** 的事项办理管理系统。面向需要对各类交办件、信访件、工单、临时任务进行登记、跟进、汇报、归档的一线工作人员。

> 所有数据只存在于你自己电脑的 SQLite 里，不上传任何服务器。

---

## ✨ 功能亮点

| 模块 | 说明 |
|---|---|
| **工作台** | 今日到期 / 临近到期 / 已超期三色分组，自动处理重复任务生成 |
| **事项台账** | 状态机严格流转、置顶、保存常用筛选、合并去重（重复件只算一次） |
| **过程时间线** | 进度 / 汇报 / 批示 / 指派 / 督办 / 办结 / 延期 / 重开 全事件聚合 |
| **汇报中心** | 内置模板 / 导入 Word 模板 / 自定义分组，一键生成 Word 文档（黑体标题 + 仿宋正文） |
| **统计分析** | 按期 / 批准延期后办结 / 超期 三桶分类，估计偏差统计，ECharts 图表 |
| **重复任务** | 固定时间触发（每日/每周/每月）或上件完成后 N 天触发，漏办也留痕 |
| **每日收尾** | 同日唯一，记录当天办结情况与统计快照 |
| **审计留痕** | 数据库触发器强制 append-only，过程记录 / 字段变更永不丢失 |
| **桌面打包** | PyInstaller onedir + pywebview 原生窗口，双击即用 |
| **全局热键** | <kbd>F9</kbd> 快速登记 · <kbd>F10</kbd> 显隐窗口 · <kbd>F11</kbd> 跳转工作台 |

---

## 🛠 技术栈

- **后端**：Python 3.12 · FastAPI · Uvicorn · SQLite（WAL 模式） · python-docx · openpyxl
- **前端**：Vue 3 · Element Plus · Vue Router · Axios · ECharts · Vite
- **打包**：PyInstaller · pywebview（EdgeWebView2） · pynput（全局热键）
- **测试**：pytest · httpx（后端 20 条用例） · Playwright（E2E 13 条）

---

## 🚀 快速开始

### 方式一：直接用打包好的 exe（推荐）

1. 下载 `release/work-ledger-win64.zip` 并解压
2. 双击 `work-ledger.exe`
3. 首次运行会在 exe 同级自动创建 `data/` 目录，你的所有记录都在里面

> 运行环境：Windows 10 / 11（64 位）。Win10 2004 以下需要先装 [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。

### 方式二：开发模式运行

```powershell
# 克隆仓库
git clone https://github.com/BuRangJiangshan/--work-ledger.exe.git
cd --work-ledger.exe

# 后端依赖
pip install -r requirements.txt
# 打包相关（可选）
pip install pyinstaller pywebview pynput

# 前端依赖
cd frontend
npm install
cd ..

# 一键开发模式（FastAPI + pywebview 同进程）
python backend/app_pack.py
```

默认监听 `http://127.0.0.1:8765`。

也可以分前后端分别启动：

```powershell
# 终端 A：FastAPI
cd backend
python run_server.py

# 终端 B：Vite 开发服务器（可选，需要改 vite.config.js 的代理）
cd frontend
npm run dev
```

---

## 📦 打包成 exe

```powershell
cd backend

# 确保前端已经构建过
cd ..\frontend
npm install
npm run build
cd ..\backend

# 打包
pyinstaller app_pack.spec --clean --noconfirm
```

产物在 `backend/dist/work-ledger/`，整个目录拷走就能用。

打包后的数据目录行为：

- **开发模式**：`work-ledger/data/`
- **exe 模式**：`exe 同级 data/`（用户可写，便于备份）
- 可通过环境变量 `APP_DATA_DIR` 强制指定

---

## 📁 项目结构

```
work-ledger/
├── backend/
│   ├── app/                     # FastAPI 应用
│   │   ├── main.py              # 入口（lifespan / 静态挂载 / CORS）
│   │   ├── config.py            # 路径、配置
│   │   ├── db.py                # SQLite 连接、初始化、在线备份
│   │   ├── schema.sql           # 建表 SQL（含审计触发器）
│   │   ├── status.py            # 状态机、标签映射
│   │   ├── audit.py             # 审计日志写入
│   │   ├── utils.py             # 工具函数
│   │   ├── routers/             # 路由层（items / workbench / reports / system）
│   │   └── services/            # 业务逻辑层（items / dashboard / reports / stats / repeats）
│   ├── tests/                   # pytest 后端测试
│   ├── app_pack.py              # 打包入口（uvicorn + pywebview + 热键）
│   ├── app_pack.spec            # PyInstaller spec
│   └── run_server.py            # 开发时简单启动
├── frontend/
│   ├── src/
│   │   ├── views/               # 9 个页面（Dashboard / ItemForm / Ledger / ItemDetail / Timeline / DailyClose / Reports / Stats / Repeats / Settings）
│   │   ├── components/          # 公共组件（StatusTag / ItemPicker）
│   │   ├── router/ store/ api/ utils/
│   │   └── App.vue              # 全局布局 + Ctrl+N 快捷键
│   ├── index.html
│   └── vite.config.js
├── .e2e/                        # Playwright E2E 测试
├── requirements.txt
├── start.bat                    # 优先用 exe，找不到则走开发模式
└── .gitignore
```

---

## 🧪 运行测试

```powershell
# 后端 pytest
cd backend
python -m pytest tests -q          # 20 条用例

# Playwright E2E（需要装 Chrome）
cd .e2e
node e2e.mjs                       # 13 条检查
```

E2E 会启动一个独立端口、独立 `APP_DATA_DIR` 的 uvicorn 实例，跑完自动清理。

---

## 💾 数据存储与备份

| 路径 | 内容 | 说明 |
|---|---|---|
| `data/app.db` | SQLite 主库 | WAL 模式，关闭时自动 checkpoint |
| `data/attachments/` | 附件文件 | 事项可上传附件 |
| `data/backups/` | 在线备份 | 系统设置里手动触发 |
| `data/uploads/` | 导入模板缓存 | 临时，不影响主数据 |

**备份方式**：完全停止程序后，把整个 `data/` 目录复制一份即可。

**审计机制**：`audit_history` 表有 `BEFORE UPDATE/DELETE` 触发器，**任何试图修改或删除旧记录的操作都会被数据库层直接拒绝**，只能追加新记录。

---

## 🎯 状态机

```
pending ──► in_process ──► review
   │  └─► assigned         │
   └─► delayed ──► in_process（解禁）
   └─► suspended ──► in_process
   └─► finished ◄── 以上任意状态
         └─► in_process（重开）
```

后端严格校验流转合法性，非法转移返回 400。

---

## ⌨️ 全局热键

| 热键 | 功能 |
|---|---|
| <kbd>F9</kbd> | 激活窗口 + 跳到「登记新事项」 |
| <kbd>F10</kbd> | 显示 / 隐藏窗口 |
| <kbd>F11</kbd> | 跳到工作台首页 |
| <kbd>Ctrl + N</kbd> | （窗口激活时）登记新事项 |

---

## 📝 许可

本项目仅供内部使用或学习交流，作者不对使用过程中产生的任何直接或间接后果负责。
