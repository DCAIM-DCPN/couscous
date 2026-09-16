#!/usr/bin/env python3
"""XFCE + Chromium + TigerVNC + noVNC launcher for Debian/Ubuntu Codespaces.

Run:
    python3 remote_desktop_codespace.py

Then open the forwarded port 6080 from the Codespaces PORTS panel.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

DISPLAY = os.environ.get("VNC_DISPLAY", ":1")
DISPLAY_NUMBER = DISPLAY.removeprefix(":")
VNC_PORT = 5900 + int(DISPLAY_NUMBER)
NOVNC_PORT = int(os.environ.get("NOVNC_PORT", "6080"))
GEOMETRY = os.environ.get("VNC_GEOMETRY", "1600x900")
LOG_DIR = Path.home() / ".codespace-desktop"
LOG_DIR.mkdir(parents=True, exist_ok=True)

processes: list[subprocess.Popen[str]] = []


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True)


def executable(name: str) -> bool:
    return shutil.which(name) is not None


def sudo_prefix() -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    if executable("sudo"):
        return ["sudo"]
    raise RuntimeError("Run this in a Debian/Ubuntu Codespace with sudo access.")


def install_packages() -> None:
    prefix = sudo_prefix()
    packages = [
        "xfce4",
        "xfce4-terminal",
        "chromium",
        "tigervnc-standalone-server",
        "novnc",
        "websockify",
        "dbus-x11",
        "x11-xserver-utils",
    ]
    run(prefix + ["apt-get", "update"])
    run(prefix + ["apt-get", "install", "-y", *packages])


def create_xstartup() -> Path:
    directory = Path.home() / ".config" / "tigervnc"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "xstartup"
    path.write_text(
        """#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_CURRENT_DESKTOP=XFCE
export XDG_CONFIG_DIRS=/etc/xdg/xdg-xfce:/etc/xdg
export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share:/usr/share
exec dbus-launch --exit-with-session startxfce4
"""
    )
    path.chmod(0o700)
    return path


def stop_old_services() -> None:
    subprocess.run(["vncserver", "-kill", DISPLAY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    for name in ("websockify", "chromium"):
        subprocess.run(["pkill", "-x", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def start_background(command: list[str], logfile: Path, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    handle = logfile.open("a", buffering=1)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
        env=merged_env,
        start_new_session=True,
        text=True,
    )
    processes.append(process)
    return process


def vnc_is_listening() -> bool:
    result = subprocess.run(["ss", "-ltn"], capture_output=True, text=True, check=False)
    return f":{VNC_PORT} " in result.stdout or f":{VNC_PORT}\n" in result.stdout


def forwarded_url() -> str:
    codespace = os.environ.get("CODESPACE_NAME")
    if codespace:
        return f"https://{codespace}-{NOVNC_PORT}.app.github.dev/vnc.html?autoconnect=true&resize=scale"
    return "Open port 6080 from the Codespaces PORTS panel, then append /vnc.html?autoconnect=true&resize=scale"


def cleanup(*_args: object) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    raise SystemExit(0)


def main() -> int:
    if not executable("apt-get"):
        raise RuntimeError("This script requires a Debian/Ubuntu-based environment.")

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("Installing required packages...", flush=True)
    install_packages()
    xstartup = create_xstartup()
    stop_old_services()

    # vncserver daemonizes. Therefore use subprocess.run, not Popen, and then verify port 5901.
    run([
        "vncserver",
        DISPLAY,
        "-geometry", GEOMETRY,
        "-depth", "24",
        "-localhost", "no",
        "-xstartup", str(xstartup),
    ])

    for _ in range(20):
        if vnc_is_listening():
            break
        time.sleep(1)
    else:
        print(f"TigerVNC did not open port {VNC_PORT}. Check ~/.vnc/*.log", file=sys.stderr)
        return 1

    print("TigerVNC is listening; launching Chromium...", flush=True)
    chromium = start_background(
        [
            "chromium",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--start-maximized",
            "https://www.youtube.com",
        ],
        LOG_DIR / "chromium.log",
        {"DISPLAY": DISPLAY},
    )

    novnc = start_background(
        [
            "websockify",
            "--web=/usr/share/novnc",
            f"0.0.0.0:{NOVNC_PORT}",
            f"127.0.0.1:{VNC_PORT}",
        ],
        LOG_DIR / "novnc.log",
    )
    time.sleep(2)
    if novnc.poll() is not None:
        print(f"noVNC exited. Check {LOG_DIR / 'novnc.log'}", file=sys.stderr)
        return 1

    print()
    print("Remote desktop is running.")
    print(f"Chromium PID: {chromium.pid}")
    print(f"noVNC URL: {forwarded_url()}")
    print(f"Logs: {LOG_DIR}")
    print("Keep this Codespace running while using the desktop.")

    # Keep the Python process alive so Codespaces does not treat the service as finished.
    while True:
        if novnc.poll() is not None:
            print("noVNC stopped; inspect ~/.codespace-desktop/novnc.log", file=sys.stderr)
            return 1
        time.sleep(5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Command failed: {error.cmd}", file=sys.stderr)
        raise SystemExit(error.returncode)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
