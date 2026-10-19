"""
AgentFlow Sandbox Harness.

Invoked in an isolated subprocess to execute untrusted user/agent code with
strict security controls:
- Network disabled (socket, urllib, http clients raise PermissionError)
- Subprocess spawning disabled (subprocess, os.system, os.popen raise PermissionError)
- Filesystem restricted (sensitive files and writing outside sandbox directory raise PermissionError)
"""
from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path
import sys
from typing import Any

# ── 1. Apply Security Controls ───────────────────────────────────────────────

# (a) Disable Network
import socket

def _blocked_network(*args: Any, **kwargs: Any) -> Any:
    raise PermissionError("Network access is disabled in the code sandbox")

socket.socket = _blocked_network  # type: ignore[assignment]
socket.create_connection = _blocked_network  # type: ignore[assignment]
if hasattr(socket, "getaddrinfo"):
    socket.getaddrinfo = _blocked_network  # type: ignore[assignment]
if hasattr(socket, "socketpair"):
    socket.socketpair = _blocked_network  # type: ignore[assignment]

try:
    import urllib.request
    urllib.request.urlopen = _blocked_network  # type: ignore[assignment]
except Exception:
    pass

try:
    import http.client
    http.client.HTTPConnection = _blocked_network  # type: ignore[misc]
    http.client.HTTPSConnection = _blocked_network  # type: ignore[misc]
except Exception:
    pass

# (b) Disable Process Spawning
import subprocess

def _blocked_process(*args: Any, **kwargs: Any) -> Any:
    raise PermissionError("Process creation is disabled in the code sandbox")

subprocess.Popen = _blocked_process  # type: ignore[misc]
subprocess.run = _blocked_process  # type: ignore[assignment]
subprocess.call = _blocked_process  # type: ignore[assignment]
subprocess.check_call = _blocked_process  # type: ignore[assignment]
subprocess.check_output = _blocked_process  # type: ignore[assignment]
os.system = _blocked_process  # type: ignore[assignment]
os.popen = _blocked_process  # type: ignore[assignment]

for fn_name in [
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp",
    "spawnvpe", "fork", "posix_spawn", "posix_spawnp", "kill", "killpg",
]:
    if hasattr(os, fn_name):
        setattr(os, fn_name, _blocked_process)

# (c) Restrict Filesystem Access
FORBIDDEN_PATH_PARTS = [
    "/etc/passwd",
    "etc/passwd",
    "/etc/shadow",
    "etc/shadow",
    "/etc/hosts",
    "etc/hosts",
    "/etc/",
    "/proc/",
    "/sys/",
    "/var/run/",
    "/root/",
    "system32",
    "windows/system32",
    ".ssh",
    ".aws",
    ".env",
    "id_rsa",
]

_orig_open = builtins.open
_sandbox_dir: str | None = None

def _is_forbidden_path(path_str: str) -> bool:
    norm = os.path.normpath(str(path_str)).replace("\\", "/").lower()
    for part in FORBIDDEN_PATH_PARTS:
        if part in norm or norm.startswith(part):
            return True
    return False

def _sandboxed_open(file: Any, *args: Any, **kwargs: Any) -> Any:
    file_str = str(file)
    if _is_forbidden_path(file_str):
        raise PermissionError(f"Access to path '{file_str}' is denied by sandbox security policy")

    mode = args[0] if args else kwargs.get("mode", "r")
    if any(m in mode for m in ("w", "a", "x", "+")):
        if _sandbox_dir:
            abs_target = os.path.abspath(file_str)
            abs_sandbox = os.path.abspath(_sandbox_dir)
            if not abs_target.startswith(abs_sandbox):
                raise PermissionError(f"Write access to '{file_str}' is denied outside sandbox directory")

    return _orig_open(file, *args, **kwargs)

builtins.open = _sandboxed_open  # type: ignore[assignment]
io.open = _sandboxed_open  # type: ignore[assignment]
Path.read_text = lambda self, *a, **k: _sandboxed_open(self, "r", *a, **k).read()  # type: ignore[method-assign]
Path.read_bytes = lambda self, *a, **k: _sandboxed_open(self, "rb", *a, **k).read()  # type: ignore[method-assign]
Path.write_text = lambda self, data, *a, **k: _sandboxed_open(self, "w", *a, **k).write(data)  # type: ignore[method-assign]
Path.write_bytes = lambda self, data, *a, **k: _sandboxed_open(self, "wb", *a, **k).write(data)  # type: ignore[method-assign]


# ── 2. Main Harness Execution ────────────────────────────────────────────────

def main() -> int:
    global _sandbox_dir
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: python -m agentflow.core.sandbox.harness <input_json> <output_json>\n")
        return 2

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    try:
        with _orig_open(input_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Failed to read input payload: {e}\n")
        return 2

    code = payload.get("code", "")
    input_data = payload.get("data", {})
    _sandbox_dir = payload.get("sandbox_dir") or os.getcwd()

    # Pre-import safe utility modules for user code
    import collections
    import datetime
    import functools
    import itertools
    import math
    import random
    import re

    safe_globals: dict[str, Any] = {
        "__builtins__": builtins.__dict__,
        "__name__": "__main__",
        "json": json,
        "math": math,
        "re": re,
        "datetime": datetime,
        "random": random,
        "collections": collections,
        "itertools": itertools,
        "functools": functools,
        "data": dict(input_data),
        "inputs": dict(input_data),
        "result": None,
        "output": None,
    }
    safe_locals: dict[str, Any] = {}

    try:
        exec(code, safe_globals, safe_locals)  # noqa: S102

        res = (
            safe_locals.get("result")
            or safe_locals.get("output")
            or safe_globals.get("result")
            or safe_globals.get("output")
        )
        if res is None:
            transform_fn = safe_locals.get("transform") or safe_globals.get("transform")
            if callable(transform_fn):
                res = transform_fn(dict(input_data))
            else:
                res = {k: v for k, v in safe_locals.items() if not k.startswith("_")} or input_data

        out_data = res if isinstance(res, dict) else {"result": res, "status": "completed"}

        result_payload = {
            "success": True,
            "data": out_data,
        }
        with _orig_open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, default=str)
        return 0

    except PermissionError as pe:
        result_payload = {
            "success": False,
            "error_type": "PermissionError",
            "error": str(pe),
        }
        try:
            with _orig_open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f)
        except Exception:
            pass
        sys.stderr.write(f"PermissionError: {pe}\n")
        return 1

    except Exception as exc:
        result_payload = {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        try:
            with _orig_open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f)
        except Exception:
            pass
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
