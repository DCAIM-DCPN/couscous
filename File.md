That means the Codespaces forwarded port is working, but noVNC cannot reach the VNC server behind it. In the Codespace terminal, run this and paste the output:

```sh
ss -ltnp | grep -E '5901|6080' || true
vncserver -list 2>&1
```

For noVNC to connect, you must see both services: VNC on `5901` and websockify on `6080`. If `5901` is missing, start TigerVNC first:

```sh
vncserver :1 -geometry 1600x900 -depth 24 -localhost no -xstartup "$HOME/.config/tigervnc/xstartup"
```

Leave that running, then in a **second Codespaces terminal** run:

```sh
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5901
```

Refresh the automatically forwarded port-6080 URL. Do not use the Android gateway for this Codespaces setup.
