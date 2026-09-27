"""Unit tests: forensic function validation + sandbox execution (master prompt §4/§8)."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.core.errors import ScriptValidationError
from app.execution.sandbox import run_function
from app.execution.validation import validate_function


def _snapshot(evidence=None):
    ev = evidence or []
    for e in ev:
        e.setdefault("data_hash", hashlib.sha256(json.dumps(e["data"], sort_keys=True).encode()).hexdigest())
    return {"investigation": {"id": "i", "name": "t"}, "evidence": ev, "timeline": [], "graph": {"edges": []}, "custody": []}


PROC = {"id": "e1", "evidence_type": "PROCESS", "data": {"pid": 9, "name": "powershell.exe", "cmdline": "powershell -enc AAAABBBBCCCCDDDDEEEEFFFFGGGG", "user": "SYSTEM", "parent_pid": 1, "parent_name": "explorer.exe"}}


def test_validation_accepts_good_function():
    info = validate_function("import forgex\ndef analyze(evidence):\n    return []\n")
    assert info["valid"] and info["entry"] == "analyze"


@pytest.mark.parametrize(
    "code",
    [
        "import os\ndef analyze(e): pass",
        "import subprocess\ndef analyze(e): pass",
        "def analyze(e):\n    open('/etc/passwd').read()",
        "def analyze(e):\n    eval('1+1')",
        "def analyze(e):\n    x = e.__class__.__subclasses__()\n    return x",
        "def helper(e): pass",  # no entry point
        "def analyze(e):",  # syntax error
    ],
)
def test_validation_rejects(code):
    with pytest.raises(ScriptValidationError):
        validate_function(code)


async def test_sandbox_runs_function_and_returns_findings():
    code = (
        "import forgex\n"
        "def analyze(evidence):\n"
        "    out = []\n"
        "    for p in evidence.processes():\n"
        "        if p.is_suspicious():\n"
        "            out.append(forgex.finding(severity='HIGH', title='suspicious ' + p.name, evidence=p, mitre=['T1059.001']))\n"
        "    forgex.log('checked', len(evidence.all()))\n"
        "    return out\n"
    )
    res = await run_function("t1", code, _snapshot([PROC]), 20)
    assert res["status"] == "COMPLETED"
    assert len(res["findings"]) == 1
    assert res["findings"][0]["evidence_ids"] == ["e1"]
    assert res["findings"][0]["mitre_techniques"] == ["T1059.001"]
    assert "checked 1" in res["console"]
    assert res["metrics"]["max_rss_mb"] > 0


async def test_sandbox_blocks_disallowed_import_at_runtime():
    res = await run_function("t2", "import socket\ndef analyze(e): return []", _snapshot(), 10)
    assert res["status"] == "SANDBOX_VIOLATION"
    assert "socket" in res["error"]["message"]


async def test_sandbox_no_filesystem_access():
    res = await run_function("t3", "def analyze(e):\n    try:\n        open('/etc/passwd')\n        return ['BAD']\n    except NameError:\n        return []\n", _snapshot(), 10)
    assert res["status"] == "COMPLETED" and res["findings"] == []
    res2 = await run_function("t4", "def analyze(e):\n    f = __import__('os').listdir('/')\n    return f", _snapshot(), 10)
    assert res2["status"] == "SANDBOX_VIOLATION"


async def test_sandbox_user_error_reported_not_crashed():
    res = await run_function("t5", "def analyze(e):\n    raise ValueError('boom')", _snapshot(), 10)
    assert res["status"] == "FAILED"
    assert res["error"]["type"] == "ValueError"
    assert "boom" in res["error"]["message"]


async def test_sandbox_cpu_limit_kills_runaway():
    res = await run_function("t6", "def analyze(e):\n    x = 0\n    while True:\n        x += 1\n", _snapshot(), 2)
    assert res["status"] in ("TIMEOUT", "FAILED", "SANDBOX_VIOLATION")


async def test_hash_verify_api_inside_sandbox():
    code = (
        "import forgex\n"
        "def analyze(evidence):\n"
        "    p = evidence.processes()[0]\n"
        "    ok1 = forgex.hash.verify(p)\n"
        "    forged = dict(p.data); forged['pid'] = 666\n"
        "    p.data = forged\n"
        "    ok2 = forgex.hash.verify(p)\n"
        "    forgex.log(f'verify={ok1} forged={ok2}')\n"
        "    return []\n"
    )
    res = await run_function("t7", code, _snapshot([PROC]), 10)
    assert res["status"] == "COMPLETED"
    assert "verify=True forged=False" in res["console"]
