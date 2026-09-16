#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

home = Path.home()
config = home / ".config" / "tigervnc"
config.mkdir(parents=True, exist_ok=True)

subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
subprocess.run([
    "sudo", "apt-get", "install", "-y",
    "xfce4", "xfce4-terminal", "chromium",
    "tigervnc-standalone-server", "novnc",
    "websockify", "dbus-x11", "x11-xserver-utils",
], check=True)

(config / "xstartup").write_text(
    "#!/bin/sh\n"
    "unset SESSION_MANAGER\n"
    "unset DBUS_SESSION_BUS_ADDRESS\n"
    "export XDG_CURRENT_DESKTOP=XFCE\n"
    "export XDG_CONFIG_DIRS=/etc/xdg/xdg-xfce:/etc/xdg\n"
    "export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share:/usr/share\n"
    "exec dbus-launch --exit-with-session startxfce4\n"
)
(config / "xstartup").chmod(0o700)

subprocess.run(["vncserver", "-kill", ":1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
subprocess.run(["pkill", "-x", "chromium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
subprocess.run(["pkill", "-x", "websockify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

subprocess.run([
    "vncserver", ":1",
    "-geometry", "1600x900",
    "-depth", "24",
    "-localhost", "no",
    "-xstartup", str(config / "xstartup"),
], check=True)

env = os.environ.copy()
env["DISPLAY"] = ":1"

subprocess.Popen(
    [
        "chromium",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--start-maximized",
        "https://www.youtube.com",
    ],
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)

subprocess.Popen(
    [
        "websockify",
        "--web=/usr/share/novnc",
        "0.0.0.0:6080",
        "127.0.0.1:5901",
    ],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
