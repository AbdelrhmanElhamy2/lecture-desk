import os
import sys
import ctypes
import subprocess
from pathlib import Path


def resolve_pythonw_executable(project_dir: Path) -> Path:
    """Prefer the project's local .venv pythonw.exe so the shortcut works without global packages."""
    venv_candidates = [
        project_dir / ".venv" / "Scripts" / "pythonw.exe",
        project_dir / "venv" / "Scripts" / "pythonw.exe",
        project_dir / ".venv" / "Scripts" / "python.exe",
        project_dir / "venv" / "Scripts" / "python.exe",
    ]
    for candidate in venv_candidates:
        if candidate.is_file():
            return candidate

    py_dir = Path(sys.executable).parent
    pythonw_exe = py_dir / "pythonw.exe"
    if pythonw_exe.is_file():
        return pythonw_exe
    return Path(sys.executable)


def create_shortcut() -> Path:
    project_dir = Path(__file__).resolve().parent
    launcher_py = project_dir / "launcher.py"
    icon_path = project_dir / "app_icon.ico"
    if not icon_path.exists():
        icon_path = project_dir / "biomedical_icon.ico"

    pythonw_exe = resolve_pythonw_executable(project_dir)

    # Detect exact Windows Desktop path dynamically (handles OneDrive Desktop redirection too)
    ps_get_desktop = "[Environment]::GetFolderPath('Desktop')"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_get_desktop],
        capture_output=True, text=True, check=True,
    )
    desktop_dir = Path(result.stdout.strip())
    if not desktop_dir.exists():
        desktop_dir = Path(os.path.expanduser("~")) / "Desktop"

    shortcut_path = desktop_dir / "Lecture Desk.lnk"
    legacy_shortcut_path = desktop_dir / "LectureAI.lnk"

    # Remove old shortcut files if present so Windows icon cache stays clean
    for old_path in (shortcut_path, legacy_shortcut_path):
        if old_path.exists():
            try:
                old_path.unlink()
            except Exception as e:
                print("Notice:", e)

    # Escape single quotes for PowerShell single-quoted string literals
    def ps_escape(val: Path) -> str:
        return str(val).replace("'", "''")

    ps_create_shortcut = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{ps_escape(shortcut_path)}')
$Shortcut.TargetPath = '{ps_escape(pythonw_exe)}'
$Shortcut.Arguments = '"{ps_escape(launcher_py)}"'
$Shortcut.WorkingDirectory = '{ps_escape(project_dir)}'
$Shortcut.IconLocation = '{ps_escape(icon_path)}, 0'
$Shortcut.Description = 'Lecture Desk — Engineering Study Suite'
$Shortcut.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_create_shortcut],
        capture_output=True, text=True, check=True,
    )

    # Notify Windows Explorer shell to refresh icons immediately
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0)
    except Exception as e:
        print("Shell notify error:", e)

    print(f"SUCCESS: Created desktop shortcut at: {shortcut_path}")
    print(f"Target: {pythonw_exe} {launcher_py}")
    print(f"Icon: {icon_path}")
    return shortcut_path


if __name__ == "__main__":
    create_shortcut()
