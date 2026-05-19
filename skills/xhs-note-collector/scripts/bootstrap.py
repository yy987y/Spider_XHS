#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_PYTHON = (3, 10)
PYTHON_WINGET_ID = "Python.Python.3.12"
NODE_WINGET_ID = "OpenJS.NodeJS.LTS"
CHROME_WINGET_ID = "Google.Chrome"
BREW_INSTALL_URL = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
PYTHON_PACKAGES = {
    "execjs": "PyExecJS",
    "requests": "requests",
    "loguru": "loguru",
    "dotenv": "python-dotenv",
    "retry": "retry",
    "openpyxl": "openpyxl",
    "aiohttp": "aiohttp",
    "cv2": "opencv-python",
    "numpy": "numpy",
    "qrcode": "qrcode",
}
CHROME_EXECUTABLE_NAMES = (
    "chrome",
    "chrome.exe",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
PYTHON_EXECUTABLE_NAMES = (
    "python",
    "python3",
    "py",
)
NODE_EXECUTABLE_NAMES = ("node", "npm")
SKILL_DIR = Path(__file__).resolve().parents[1]
BUNDLED_RUNTIME_DIR = SKILL_DIR / "runtime"


class BootstrapError(RuntimeError):
    pass


def _is_runtime_dir(path: Path) -> bool:
    return (
        (path / "spider" / "collect_notes.py").exists()
        and (path / "apis" / "xhs_pc_login_apis.py").exists()
        and (path / "xhs_utils" / "xhs_util.py").exists()
        and (path / "static" / "xhs_main_260411.js").exists()
        and (path / "requirements.txt").exists()
        and (path / "package.json").exists()
    )


def find_repo(start: Path | None = None) -> Path:
    env_repo = os.environ.get("XHS_NOTE_COLLECTOR_REPO")
    if env_repo:
        env_path = Path(env_repo).expanduser().resolve()
        if _is_runtime_dir(env_path):
            return env_path
        raise BootstrapError(f"XHS_NOTE_COLLECTOR_REPO 指向的目录不是可运行 runtime: {env_path}")

    if _is_runtime_dir(BUNDLED_RUNTIME_DIR):
        return BUNDLED_RUNTIME_DIR

    start = (start or Path.cwd()).resolve()
    for path in [start, *start.parents]:
        if _is_runtime_dir(path):
            return path
    raise BootstrapError("未找到 xhs-note-collector 内置 runtime，请确认 skill 分发包完整。")


def _missing_python_modules() -> list[str]:
    missing = []
    for module_name, package_name in PYTHON_PACKAGES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def _run(cmd: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        output = (completed.stdout or "").strip()
        raise BootstrapError(
            "环境自动初始化失败：\n"
            + " ".join(cmd)
            + (f"\n{output}" if output else "")
        )


def _run_shell(command: str, *, cwd: Path) -> None:
    shell = os.environ.get("SHELL") or "/bin/sh"
    _run([shell, "-lc", command], cwd=cwd)


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _is_macos() -> bool:
    return platform.system().lower() == "darwin"


def _is_linux() -> bool:
    return platform.system().lower() == "linux"


def _winget() -> str | None:
    return shutil.which("winget")


def _run_winget_install(package_id: str, *, cwd: Path) -> None:
    winget = _winget()
    if not winget:
        raise BootstrapError(
            "未找到 winget，无法自动静默安装系统级软件。请使用 Windows 10/11 并确认 App Installer 可用。"
        )
    _run(
        [
            winget,
            "install",
            "--id",
            package_id,
            "--exact",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        cwd=cwd,
    )


def _refresh_path_from_windows_install_locations() -> None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "Scripts",
        Path(os.environ.get("PROGRAMFILES", "")) / "nodejs",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])


def _brew() -> str | None:
    _refresh_path_from_windows_install_locations()
    return shutil.which("brew")


def _ensure_brew(repo: Path) -> str:
    brew = _brew()
    if brew:
        return brew
    _run_shell(f'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL {BREW_INSTALL_URL})"', cwd=repo)
    _refresh_path_from_windows_install_locations()
    brew = _brew()
    if not brew:
        raise BootstrapError("Homebrew 自动安装后仍不可用。")
    return brew


def _sudo_prefix() -> str:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ""
    return "sudo -n "


def _sudo_env_prefix(env: str) -> str:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return env + " "
    return f"sudo -n env {env} "


def _linux_install(packages: list[str], *, cwd: Path) -> None:
    sudo = _sudo_prefix()
    if shutil.which("apt-get"):
        _run_shell(f"{sudo}apt-get update", cwd=cwd)
        _run_shell(
            _sudo_env_prefix("DEBIAN_FRONTEND=noninteractive")
            + "apt-get install -y "
            + " ".join(packages),
            cwd=cwd,
        )
        return
    if shutil.which("dnf"):
        _run_shell(f"{sudo}dnf install -y " + " ".join(packages), cwd=cwd)
        return
    if shutil.which("yum"):
        _run_shell(f"{sudo}yum install -y " + " ".join(packages), cwd=cwd)
        return
    if shutil.which("pacman"):
        _run_shell(f"{sudo}pacman -Sy --noconfirm " + " ".join(packages), cwd=cwd)
        return
    raise BootstrapError("未找到 apt-get、dnf、yum 或 pacman，无法自动安装系统级软件。")


def _install_python_runtime(repo: Path) -> None:
    if _is_windows():
        _run_winget_install(PYTHON_WINGET_ID, cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_macos():
        brew = _ensure_brew(repo)
        _run([brew, "install", "python@3.12"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_linux():
        _linux_install(["python3", "python3-pip"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    raise BootstrapError(f"暂不支持自动安装 Python 的系统：{platform.system()}")


def _install_node_runtime(repo: Path) -> None:
    if _is_windows():
        _run_winget_install(NODE_WINGET_ID, cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_macos():
        brew = _ensure_brew(repo)
        _run([brew, "install", "node"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_linux():
        _linux_install(["nodejs", "npm"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    raise BootstrapError(f"暂不支持自动安装 Node.js 的系统：{platform.system()}")


def _install_chrome_runtime(repo: Path) -> None:
    if _is_windows():
        _run_winget_install(CHROME_WINGET_ID, cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_macos():
        brew = _ensure_brew(repo)
        _run([brew, "install", "--cask", "google-chrome"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    if _is_linux():
        try:
            _linux_install(["chromium"], cwd=repo)
        except BootstrapError:
            _linux_install(["chromium-browser"], cwd=repo)
        _refresh_path_from_windows_install_locations()
        return
    raise BootstrapError(f"暂不支持自动安装 Chrome/Chromium 的系统：{platform.system()}")


def _version_tuple(value: str) -> tuple[int, ...]:
    digits = []
    for part in value.strip().lstrip("v").split("."):
        if not part.isdigit():
            break
        digits.append(int(part))
    return tuple(digits)


def _candidate_chrome_paths() -> list[Path]:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/opt/google/chrome/google-chrome"),
    ]
    program_files = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for root in program_files:
        if not root:
            continue
        candidates.extend(
            [
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(root) / "Chromium" / "Application" / "chrome.exe",
            ]
        )
    return candidates


def find_chrome_executable() -> str | None:
    for name in CHROME_EXECUTABLE_NAMES:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    for path in _candidate_chrome_paths():
        if path.exists():
            return str(path)
    return None


def _check_python_runtime(repo: Path) -> None:
    if tuple(sys.version_info[:2]) < REQUIRED_PYTHON:
        current = ".".join(str(part) for part in sys.version_info[:3])
        try:
            _install_python_runtime(repo)
        except BootstrapError as exc:
            raise BootstrapError(f"Python 版本过低：{current}，且自动安装失败：{exc}") from exc
        raise BootstrapError(
            f"Python 已尝试自动安装，但当前进程仍是 {current}。请重新启动 Agent 后再运行。"
        )


def _check_node(repo: Path, *, install_system: bool = True) -> None:
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        if install_system:
            try:
                _install_node_runtime(repo)
            except BootstrapError as exc:
                raise BootstrapError(f"未找到 Node.js/npm，自动安装失败：{exc}") from exc
            node = shutil.which("node")
            npm = shutil.which("npm")
        if not node or not npm:
            raise BootstrapError("未找到 Node.js/npm，且自动安装后仍不可用。请重新启动 Agent 后再运行。")
    version = subprocess.run(
        [node, "--version"],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout.strip()
    if _version_tuple(version) < (20,):
        if install_system:
            try:
                _install_node_runtime(repo)
            except BootstrapError as exc:
                raise BootstrapError(f"Node.js 版本过低：{version or '未知'}，自动安装失败：{exc}") from exc
            version = subprocess.run(
                [shutil.which("node") or node, "--version"],
                cwd=str(repo),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ).stdout.strip()
        if _version_tuple(version) < (20,):
            raise BootstrapError(f"Node.js 版本过低：{version or '未知'}。自动安装后仍需 Node.js 20+。")
    if (repo / "package.json").exists() and not (repo / "node_modules").exists():
        _run([npm, "install"], cwd=repo)


def _check_chrome(repo: Path, *, install_system: bool = True) -> None:
    if find_chrome_executable():
        return
    if install_system:
        try:
            _install_chrome_runtime(repo)
        except BootstrapError as exc:
            raise BootstrapError(f"未找到 Google Chrome/Chromium，自动安装失败：{exc}") from exc
    if not find_chrome_executable():
        raise BootstrapError("未找到 Google Chrome，且自动安装后仍不可用。详情补全依赖 Chrome。")


def ensure_environment(repo: Path | None = None, *, install_system: bool = True) -> Path:
    repo = repo or find_repo()
    _check_python_runtime(repo)
    _refresh_path_from_windows_install_locations()
    missing = _missing_python_modules()
    requirements = repo / "requirements.txt"
    if missing and requirements.exists():
        _run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], cwd=repo)
        missing = _missing_python_modules()
    if missing:
        raise BootstrapError("Python 依赖仍缺失：" + "、".join(missing))

    _check_node(repo, install_system=install_system)
    _check_chrome(repo, install_system=install_system)

    return repo


def main() -> None:
    repo = find_repo()
    ensure_environment(repo)
    print("环境检查通过")


if __name__ == "__main__":
    main()
