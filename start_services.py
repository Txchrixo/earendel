#!/usr/bin/env python3
"""Daemonize the Next.js dev server + FastAPI backend so they survive the
parent bash session exiting. Uses start_new_session=True (setsid) plus a
pidfile. Run: python3 /home/z/my-project/start_services.py"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/z/my-project")
PIDFILE = ROOT / "services.pid"


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pids() -> dict[str, int]:
    if PIDFILE.exists():
        out = {}
        for line in PIDFILE.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = int(v)
        return out
    return {}


def kill_pid(pid: int) -> None:
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def start() -> None:
    pids = read_pids()
    # Kill old instances
    for key in ("next", "backend", "mcp"):
        if key in pids and is_alive(pids[key]):
            print(f"killing old {key} pid={pids[key]}")
            kill_pid(pids[key])
            time.sleep(1.5)

    # Start Next.js dev server (port 3000)
    next_proc = subprocess.Popen(
        ["bun", "run", "dev"],
        cwd=str(ROOT),
        stdout=open(ROOT / "dev.log", "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Start FastAPI backend (port 8001)
    backend_proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd=str(ROOT / "backend"),
        stdout=open(ROOT / "backend.log", "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Start MCP server (port 3004)
    mcp_proc = subprocess.Popen(
        ["bun", "run", "index.ts"],
        cwd=str(ROOT / "mini-services" / "mcp-server"),
        stdout=open(ROOT / "mcp-server.log", "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    PIDFILE.write_text(
        f"next={next_proc.pid}\nbackend={backend_proc.pid}\nmcp={mcp_proc.pid}\n"
    )
    print(f"started next={next_proc.pid} backend={backend_proc.pid} mcp={mcp_proc.pid}")
    # Wait for all to be ready
    import urllib.request
    for label, port, path in (
        ("next", 3000, "/"),
        ("backend", 8001, "/api/v1/healthz?XTransformPort=8001"),
        ("mcp", 3004, "/health"),
    ):
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=1)
                print(f"{label} ready on {port}")
                break
            except Exception:
                time.sleep(0.5)
        else:
            print(f"WARNING: {label} not responding on {port}")


if __name__ == "__main__":
    start()
