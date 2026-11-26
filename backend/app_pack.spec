# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 事项办理全程留痕工具

用法：
    pyinstaller app_pack.spec --clean --noconfirm

产物：dist/work-ledger/work-ledger.exe
"""
from pathlib import Path
import sys

block_cipher = None

# -------- 路径 --------
BACKEND = Path(".").resolve()
PROJECT = BACKEND.parent
FRONTEND_DIST = PROJECT / "frontend" / "dist"
SCHEMA_SQL = BACKEND / "app" / "schema.sql"

# -------- datas --------
# (源路径, 打包后在 _MEIPASS 里的相对目录)
datas = [
    # schema.sql 放到 app/ 下（config.py frozen 时读 _MEIPASS/app/schema.sql）
    (str(SCHEMA_SQL), "app"),
    # 前端静态文件放到 frontend/dist/ 下
    (str(FRONTEND_DIST), "frontend/dist"),
]

# -------- hiddenimports --------
# FastAPI 的路由通过字符串引用 "app.main:app"，PyInstaller 可能漏扫
hiddenimports = [
    "app",
    "app.main",
    "app.config",
    "app.db",
    "app.audit",
    "app.status",
    "app.utils",
    "app.routers",
    "app.routers.items",
    "app.routers.workbench",
    "app.routers.reports",
    "app.routers.system",
    "app.services",
    "app.services.items",
    "app.services.dashboard",
    "app.services.repeats",
    "app.services.reports",
    "app.services.settings",
    "app.services.stats",
    # 第三方运行时隐式导入
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "pydantic",
    "docx",
    "openpyxl",
    # pywebview 后端
    "webview",
    "webview.platforms",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    # pynput
    "pynput",
    "pynput.keyboard",
    "pynput.mouse",
]

# pywebview 的 pythonnet / clr_loader 需要的依赖
hiddenimports += [
    "clr_loader",
    "pythonnet",
    "System",
]

a = Analysis(
    ["app_pack.py"],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                  # onedir: binaries/datas/zipfiles 交给 COLLECT
    exclude_binaries=True,
    name="work-ledger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # 正式发布：不显示黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="work-ledger",
)
