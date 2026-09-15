#!/usr/bin/env python3
"""Install and launch an XFCE + Chromium + TigerVNC + noVNC desktop.

Designed for Debian/Ubuntu-based GitHub Codespaces and similar Linux hosts.
Run with: python3 remote_desktop_codespace.py
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

PORT = int(os.environ.get("NOVNC_PORT", "6080"))
DISPLAY = os.environ.get("VNC_DISPLAY", ":1")
GEOMETRY = os.environ.get("VNC_GEOMETRY", "1600x900")
DISPLAY_NUM = DISPLAY.lstrip(":")
VNC_PORT = 5900 + int(DISPLAY_NUM)
BASE = Path.home() / ".codespace-desktop"
BASE.mkdir(parents=True, exist_ok=True)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def apt_prefix() -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    if command_exists("sudo"):
        return ["sudo"]
    raise RuntimeError("This script needs root or sudo to install Debian packages.")


def install_packages() -> None:
    prefix = apt_prefix()
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


def write_xstartup() -> Path:
    config_dir = Path.home() / ".config" / "tigervnc"
    config_dir.mkdir(parents=True, exist_ok=True)
    startup = config_dir / "xstartup"
    startup.write_text(
        """#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_CURRENT_DESKTOP=XFCE
export XDG_CONFIG_DIRS=/etc/xdg/xdg-xfce:/etc/xdg
export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share:/usr/share
exec dbus-launch --exit-with-session startxfce4
"""
    )
    startup.chmod(0o700)
    return startup


def stop_existing() -> None:
    subprocess.run(
        ["vncserver", "-kill", DISPLAY],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    for name in ("websockify", "chromium"):
        subprocess.run(["pkill", "-x", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def start_process(command: list[str], log_name: str) -> subprocess.Popen[str]:
    log = open(BASE / log_name, "a", buffering=1)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )
    return process


def codespaces_url() -> str:
    name = os.environ.get("CODESPACE_NAME")
    if name:
        return f"https://{name}-{PORT}.app.github.dev/vnc.html?autoconnect=true&resize=scale"
    return f"Open the forwarded port {PORT} in the Codespaces PORTS tab, then append /vnc.html?autoconnect=true&resize=scale"


def main() -> int:
    if not command_exists("apt-get"):
        print("This script expects a Debian/Ubuntu-based Linux environment.", file=sys.stderr)
        return 2

    print("Installing desktop packages. This may take several minutes...", flush=True)
    install_packages()
    startup = write_xstartup()
    stop_existing()

    vnc = start_process(
        [
            "vncserver",
            DISPLAY,
            "-geometry",
            GEOMETRY,
            "-depth",
            "24",
            "-localhost",
            "no",
            "-xstartup",
            str(startup),
        ],
        "vnc.log",
    )
    time.sleep(5)
    if vnc.poll() is not None:
        print(f"TigerVNC exited; inspect {BASE / 'vnc.log'}", file=sys.stderr)
        return 1

    chromium = start_process(
        [
            "chromium",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--start-maximized",
            "https://www.youtube.com",
        ],
        "chromium.log",
    )

    novnc = start_process(
        [
            "websockify",
            f"--web=/usr/share/novnc",
            f"0.0.0.0:{PORT}",
            f"127.0.0.1:{VNC_PORT}",
        ],
        "novnc.log",
    )
    time.sleep(2)
    if novnc.poll() is not None:
        print(f"noVNC exited; inspect {BASE / 'novnc.log'}", file=sys.stderr)
        return 1

    print()
    print("Remote desktop is running.")
    print(f"Display: {DISPLAY}   Geometry: {GEOMETRY}")
    print(f"noVNC URL: {codespaces_url()}")
    print(f"Logs: {BASE}")
    print("In GitHub Codespaces, open the PORTS tab and make port 6080 visible to your intended audience.")
    print("Keep this Codespace running while you use the desktop.")
    print(f"PIDs: VNC={vnc.pid}, Chromium={chromium.pid}, noVNC={novnc.pid}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nLauncher interrupted. Background processes may still be running; use vncserver -kill :1 and pkill websockify to stop them.")
        raise SystemExit(130)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {exc.cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
