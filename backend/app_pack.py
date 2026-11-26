"""打包入口：同进程启动 FastAPI + pywebview 窗口 + 全局热键。

使用方法：
  python app_pack.py      # 开发模式（直接运行）
  pyinstaller app_pack.spec  # 打包成 exe
"""
from __future__ import annotations

import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# --------- frozen 模式下的异常日志 ---------
def _setup_crash_log() -> None:
    """把未捕获异常写到 exe 同级的 crash.log，便于定位 console=False 时的崩溃。"""
    if not getattr(sys, "frozen", False):
        return
    try:
        exe_dir = Path(sys.executable).resolve().parent
        log_path = exe_dir / "crash.log"

        def _excepthook(exc_type, exc_value, exc_tb):
            try:
                from datetime import datetime
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n=== {datetime.now()} ===\n")
                    traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            except Exception:
                pass
            # 恢复默认行为（进程退出码 1）
            sys.__excepthook__(exc_type, exc_value, exc_tb)

        sys.excepthook = _excepthook
    except Exception:
        pass

_setup_crash_log()

# --------- 路径解析：兼容 PyInstaller frozen ---------
def _resolve_base() -> Path:
    """打包后 sys._MEIPASS 指向解压目录，开发时用脚本所在目录。"""
    if getattr(sys, "frozen", False):
        # PyInstaller onefile/onedir 解压目录（含打包进的资源）
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

BASE_DIR = _resolve_base()
# 开发时 backend/ 作为 BASE_DIR，打包后就是解压根
sys.path.insert(0, str(BASE_DIR))

# frozen 后 frontend/dist 和 schema.sql 会被 PyInstaller 放到 _MEIPASS 下
# 所以 config.py 的 FRONTEND_DIST / SCHEMA_PATH 需要跟着 BASE_DIR 走
# 这里我们直接 monkey-patch 环境变量，让 config.py 走 frozen 路径
import os  # noqa: E402
os.environ["_LEDGER_FROZEN"] = "1"

# 启动 uvicorn
import uvicorn  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765

# pywebview 延迟导入（避免没有 WebView2 时直接崩）
try:
    import webview  # type: ignore
    HAS_WEBVIEW = True
except Exception as e:  # noqa: BLE001
    HAS_WEBVIEW = False
    print(f"[WARN] pywebview 不可用，将回退到浏览器模式: {e}")


def _run_uvicorn() -> None:
    """同进程后台线程跑 FastAPI。"""
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


def _wait_server(url: str, timeout: float = 10.0) -> bool:
    """简单轮询 /api/health 直到返回 200。"""
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.3)
    return False


class _AppController:
    """全局状态 + 热键回调。"""

    def __init__(self) -> None:
        self.window = None
        self._visible = True

    def show_window(self) -> None:
        if self.window is None:
            return
        self.window.restore()
        self.window.focus()
        self._visible = True

    def hide_window(self) -> None:
        if self.window is None:
            return
        self.window.minimize()
        self._visible = False

    def toggle_window(self) -> None:
        if self._visible:
            self.hide_window()
        else:
            self.show_window()

    def quick_new_item(self) -> None:
        """F9：激活窗口并导航到「登记新事项」。"""
        if self.window is None:
            return
        self.show_window()
        # 通过 js 导航到 #/item/new
        try:
            self.window.evaluate_js(
                "location.hash = '#/item/new'; window.dispatchEvent(new HashChangeEvent('hashchange'));"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] quick_new_item js error: {e}")


def _setup_hotkeys(ctrl: _AppController) -> None:
    """注册全局热键。"""
    if not HAS_WEBVIEW:
        return
    try:
        from pynput import keyboard  # type: ignore

        def _on_press(key) -> None:
            try:
                k = key.char if hasattr(key, "char") and key.char else key.name
            except Exception:  # noqa: BLE001
                k = str(key)
            if k == "f9":
                ctrl.quick_new_item()
            elif k == "f10":
                ctrl.toggle_window()
            elif k == "f11":
                # F11：工作台
                if ctrl.window:
                    ctrl.show_window()
                    ctrl.window.evaluate_js(
                        "location.hash = '#/dashboard'; window.dispatchEvent(new HashChangeEvent('hashchange'));"
                    )

        listener = keyboard.Listener(on_press=_on_press)
        listener.daemon = True
        listener.start()
        print("[INFO] 全局热键已注册：F9 快速登记 | F10 显示/隐藏窗口 | F11 工作台")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 热键注册失败: {e}")


def main() -> None:
    # 1) 后台启动 FastAPI
    server_thread = threading.Thread(target=_run_uvicorn, daemon=True, name="uvicorn")
    server_thread.start()

    # 2) 等待服务就绪
    health_url = f"http://{HOST}:{PORT}/api/health"
    if not _wait_server(health_url):
        print("[ERROR] FastAPI 启动超时")
        sys.exit(1)
    print(f"[INFO] 服务已就绪 http://{HOST}:{PORT}")

    # 3) 启动 pywebview 窗口
    url = f"http://{HOST}:{PORT}/"
    ctrl = _AppController()
    webview_ok = False

    if HAS_WEBVIEW:
        try:
            _setup_hotkeys(ctrl)
            ctrl.window = webview.create_window(
                title="事项办理全程留痕工具",
                url=url,
                width=1280,
                height=800,
                min_size=(960, 600),
                text_select=True,
            )
            print("[INFO] pywebview 窗口已创建，启动事件循环...")
            webview.start()
            webview_ok = True
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] pywebview 启动失败，回退到浏览器: {e}")
            webview_ok = False

    if not webview_ok:
        # 回退：直接打开浏览器
        webbrowser.open(url)
        print("[INFO] 已用默认浏览器打开应用。")

    # 4) 不管 webview 是否可用，主线程都挂起（daemon 线程随主线程退出）
    #    用户关闭 pywebview 窗口后走到这里，或者一开始就走浏览器模式
    print("[INFO] 进程保活中...（关闭最后一个窗口或托盘图标退出）")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] 收到中断，退出")
        sys.exit(0)


if __name__ == "__main__":
    main()
