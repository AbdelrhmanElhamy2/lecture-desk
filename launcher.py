import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8000"
CONFIG_URL = f"{URL}/api/config"
ERROR_LOG = PROJECT_DIR / "launcher_error.log"


def is_server_running() -> bool:
    try:
        req = urllib.request.Request(CONFIG_URL, headers={"User-Agent": "LectureDesk-Launcher"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def resolve_python_executable() -> Path:
    """Prefer the project's local .venv Python when available, otherwise use the active interpreter."""
    if sys.platform == "win32":
        venv_candidates = [
            PROJECT_DIR / ".venv" / "Scripts" / "python.exe",
            PROJECT_DIR / "venv" / "Scripts" / "python.exe",
        ]
    else:
        venv_candidates = [
            PROJECT_DIR / ".venv" / "bin" / "python",
            PROJECT_DIR / ".venv" / "bin" / "python3",
            PROJECT_DIR / "venv" / "bin" / "python",
            PROJECT_DIR / "venv" / "bin" / "python3",
        ]

    for candidate in venv_candidates:
        if candidate.is_file():
            return candidate

    # Use python.exe (not pythonw.exe) to run uvicorn cleanly in the background
    py_exe = Path(sys.executable)
    if py_exe.name.lower() == "pythonw.exe":
        normal_py = py_exe.parent / "python.exe"
        if normal_py.exists():
            py_exe = normal_py
    return py_exe


def start_server() -> bool:
    if is_server_running():
        return True

    py_exe = resolve_python_executable()
    cmd = [
        str(py_exe),
        "-m", "uvicorn",
        "app:app",
        "--host", "127.0.0.1",
        "--port", "8000",
    ]

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creation_flags |= subprocess.DETACHED_PROCESS

    stderr_file = open(ERROR_LOG, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_DIR),
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        stderr_file.close()
        raise

    # Wait up to ~20s for first-boot imports (e.g. Matplotlib font cache on fresh installs)
    started = False
    for _ in range(65):
        time.sleep(0.3)
        if is_server_running():
            started = True
            break
        if proc.poll() is not None:
            break

    stderr_file.close()
    if started:
        try:
            ERROR_LOG.unlink(missing_ok=True)
        except OSError:
            pass
    return started


def find_app_browser() -> str:
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]

    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def open_app_window() -> None:
    browser_exe = find_app_browser()
    if browser_exe:
        try:
            subprocess.Popen(
                [browser_exe, f"--app={URL}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

    webbrowser.open(URL)


def show_startup_error() -> None:
    msg = (
        "Lecture Desk could not start its local server.\n\n"
        "Try running Start_Lecture_Desk.bat (Windows) or Start_Lecture_Desk.command (Mac) "
        f"to repair the setup.\n\nDetails were saved to:\n{ERROR_LOG}"
    )
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Lecture Desk — Startup Notice", 0x10)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def main() -> None:
    if start_server():
        open_app_window()
    else:
        show_startup_error()


if __name__ == "__main__":
    main()
