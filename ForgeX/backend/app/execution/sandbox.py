"""Sandbox controller: launches the restricted child runtime, enforces timeout, supports stop."""
from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from app.config import get_settings
from app.core.logging import get_logger

log = get_logger("sandbox")
settings = get_settings()

SDK_PATH = Path(__file__).resolve().parents[2] / "forgex_sdk"
_RUNNING: dict[str, asyncio.subprocess.Process] = {}


def _secure_write(content: str) -> str:
    fd, path = tempfile.mkstemp(prefix="forgex_sbx_", dir=settings.data_dir, text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


async def run_function(execution_id: str, code: str, snapshot: dict, timeout_sec: int) -> dict:
    snap_path = _secure_write(json.dumps(snapshot, default=str))
    code_path = _secure_write(code)
    out_path = _secure_write("")
    env = {
        "PYTHONPATH": str(SDK_PATH),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(settings.data_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "forgex._runtime", snap_path, code_path, out_path, str(timeout_sec),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(settings.data_dir),
    )
    _RUNNING[execution_id] = proc
    try:
        try:
            _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec + 5)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "TIMEOUT",
                "findings": [],
                "console": [],
                "error": {"type": "ExecutionTimeout", "message": f"Function exceeded the {timeout_sec}s execution limit and was terminated.", "traceback": ""},
                "metrics": {},
            }
        try:
            raw = Path(out_path).read_text()
        except OSError:
            raw = ""
        try:
            result = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            result = {}
        if not isinstance(result, dict) or "status" not in result:
            rc = proc.returncode
            killed_by_signal = rc is not None and rc < 0
            result = {
                "status": "TIMEOUT" if killed_by_signal else "FAILED",
                "findings": [],
                "console": [],
                "error": {
                    "type": "ExecutionTimeout" if killed_by_signal else "SandboxCrash",
                    "message": (
                        "Function was terminated by the sandbox resource limiter (CPU time or memory limit exceeded)."
                        if killed_by_signal
                        else (stderr.decode("utf-8", "replace") or "child process produced no result")[:500]
                    ),
                    "traceback": "",
                },
                "metrics": {},
            }
        result.setdefault("exit_code", proc.returncode)
        return result
    finally:
        _RUNNING.pop(execution_id, None)
        for p in (snap_path, code_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


async def stop_function(execution_id: str) -> bool:
    proc = _RUNNING.get(execution_id)
    if not proc:
        return False
    proc.kill()
    return True
