"""
Sandbox runner for isolated execution of user/agent code.

Supports:
1. Ephemeral Docker containers (--network=none --memory=256m --cpus=0.5) when available.
2. Isolated subprocesses with sanitized environment, security guards, and timeout limits.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class SandboxError(Exception):
    """Base exception for code sandbox failures."""


class SandboxSecurityError(SandboxError):
    """Raised when user code attempts an unauthorized security action (network, forbidden filesystem, etc.)."""


class SandboxExecutionError(SandboxError):
    """Raised when user code encounters a runtime, syntax, or logical error."""


class SandboxTimeoutError(SandboxError):
    """Raised when user code execution exceeds the allocated timeout."""


def is_docker_available() -> bool:
    """Return True if Docker CLI and daemon are reachable and not explicitly disabled."""
    if os.environ.get("AGENTFLOW_SANDBOX_DRIVER", "").lower() == "subprocess":
        return False
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def run_in_sandbox_sync(
    code: str,
    input_data: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
    memory_limit_mb: int = 256,
) -> dict[str, Any]:
    """
    Synchronously execute untrusted code in an isolated sandbox.

    Never executes within the host Python process.
    """
    clean_inputs = dict(input_data or {})
    scratch_dir = tempfile.mkdtemp(prefix="agentflow_sandbox_")
    scratch_path = Path(scratch_dir)

    input_file = scratch_path / "input.json"
    output_file = scratch_path / "output.json"

    payload = {
        "code": code,
        "data": clean_inputs,
        "sandbox_dir": str(scratch_path.resolve()),
    }

    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    # Locate backend/src for PYTHONPATH resolution
    current_file = Path(__file__).resolve()
    backend_src = current_file.parents[3]  # .../backend/src

    use_docker = is_docker_available()

    try:
        if use_docker:
            # Ephemeral container execution
            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                f"--memory={memory_limit_mb}m",
                "--cpus=0.5",
                "-v", f"{scratch_path.resolve()}:/sandbox",
                "-w", "/sandbox",
                "-e", "PYTHONPATH=/sandbox",
                "python:3.12-slim",
                "python", "-m", "agentflow.core.sandbox.harness",
                "/sandbox/input.json",
                "/sandbox/output.json",
            ]
            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise SandboxTimeoutError(f"Container sandbox execution timed out after {timeout_seconds}s") from exc
        else:
            # Subprocess execution with sanitized environment
            safe_env: dict[str, str] = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(backend_src),
                "TMP": str(scratch_path),
                "TEMP": str(scratch_path),
                "PYTHONUNBUFFERED": "1",
            }
            if sys.platform == "win32":
                for k in ("SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC"):
                    if k in os.environ:
                        safe_env[k] = os.environ[k]

            cmd = [
                sys.executable,
                "-m",
                "agentflow.core.sandbox.harness",
                str(input_file),
                str(output_file),
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(scratch_path),
                    env=safe_env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise SandboxTimeoutError(f"Code sandbox execution timed out after {timeout_seconds}s") from exc

        # Parse structured output from harness
        if output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    res_data = json.load(f)
                if res_data.get("success"):
                    return res_data.get("data", {})
                error_type = res_data.get("error_type", "Error")
                error_msg = res_data.get("error", "Execution failed")
                if error_type == "PermissionError":
                    raise SandboxSecurityError(error_msg)
                raise SandboxExecutionError(f"{error_type}: {error_msg}")
            except (json.JSONDecodeError, OSError) as e:
                log.warning("failed_to_read_sandbox_output", error=str(e))

        # Check process status and stderr
        stderr = proc.stderr.strip()
        if "PermissionError" in stderr:
            raise SandboxSecurityError(stderr)

        if proc.returncode != 0:
            raise SandboxExecutionError(stderr or f"Sandbox process failed with return code {proc.returncode}")

        return clean_inputs

    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


async def run_in_sandbox(
    code: str,
    input_data: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
    memory_limit_mb: int = 256,
) -> dict[str, Any]:
    """Asynchronously execute untrusted code in an isolated sandbox thread."""
    return await asyncio.to_thread(
        run_in_sandbox_sync,
        code=code,
        input_data=input_data or {},
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
    )
