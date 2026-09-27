"""ForgeX sandbox child runtime.

Executes a user forensic function with:
  * import allow-list enforced via sys.meta_path
  * restricted builtins (no open/exec/eval/__import__/compile/input)
  * OS resource limits (CPU, address space, file size, fds)
  * deterministic JSON output envelope (findings, console, metrics)
"""
from __future__ import annotations

import inspect
import io
import json
import resource
import sys
import traceback
from contextlib import redirect_stdout

ALLOWED_MODULES = {
    "forgex", "json", "re", "datetime", "collections", "math", "statistics",
    "hashlib", "itertools", "functools", "typing", "enum", "string", "operator",
}


class ImportBlocker:
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root not in ALLOWED_MODULES:
            raise ImportError(f"ForgeX sandbox policy: import of '{fullname}' is not permitted. Allowed modules: {sorted(ALLOWED_MODULES)}")
        return None


SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "format",
        "frozenset", "int", "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min",
        "next", "print", "range", "repr", "reversed", "round", "set", "slice", "sorted", "str",
        "sum", "tuple", "zip", "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "NameError", "AttributeError", "ZeroDivisionError", "StopIteration", "RuntimeError",
        "ArithmeticError", "LookupError", "OverflowError", "UnicodeDecodeError", "UnicodeEncodeError",
    )
    if (isinstance(__builtins__, dict) and name in __builtins__) or (not isinstance(__builtins__, dict) and hasattr(__builtins__, name))
}

_real_import = __import__


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Import gate for user code. Blocks non-allow-listed roots even when the
    module is already in sys.modules (which would bypass meta_path finders)."""
    root = name.split(".")[0] if name else ""
    if level == 0 and root not in ALLOWED_MODULES:
        raise ImportError(
            f"ForgeX sandbox policy: import of '{name}' is not permitted. "
            f"Allowed modules: {sorted(ALLOWED_MODULES)}"
        )
    return _real_import(name, globals, locals, fromlist, level)


SAFE_BUILTINS["__import__"] = _safe_import


def _set_limits(timeout_sec: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_sec, timeout_sec + 5))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    except (ValueError, OSError):
        pass
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    except (ValueError, OSError):
        pass


def _find_entry(env: dict):
    for name in ("analyze", "main"):
        if callable(env.get(name)):
            return env[name]
    for name, obj in env.items():
        if name.startswith("analyze_") and callable(obj) and not name.startswith("_"):
            return obj
    return None


def main(argv: list[str]) -> int:
    snapshot_path, code_path, output_path, timeout_s = argv[1], argv[2], argv[3], int(argv[4])
    _set_limits(timeout_s)
    sys.meta_path.insert(0, ImportBlocker())
    result: dict = {"status": "FAILED", "findings": [], "console": [], "error": None, "metrics": {}}
    buf = io.StringIO()
    try:
        snapshot = json.loads(open(snapshot_path, encoding="utf-8").read()) if _allowed_read() else {}
    except OSError as e:
        snapshot = {}
        result["console"].append(f"snapshot read failed: {e}")
    try:
        import forgex

        rt = forgex._bind(snapshot)
        code = open(code_path, encoding="utf-8").read() if _allowed_read() else ""
        env = {"__builtins__": SAFE_BUILTINS, "__name__": "__forgex_function__"}
        with redirect_stdout(buf):
            exec(compile(code, "<forgex-function>", "exec"), env)
            entry = _find_entry(env)
            if entry is None:
                raise forgex.ForgeXError(
                    "No entry point found. Define `def analyze(evidence):` (or `main(evidence)`) in your forensic function."
                )
            params = list(inspect.signature(entry).parameters)
            args = (rt.load_evidence(),) if len(params) >= 1 else ()
            entry(*args)
        result["status"] = "COMPLETED"
        result["findings"] = rt.findings
        result["console"] = rt.console + buf.getvalue().splitlines()
    except ImportError as e:
        result["status"] = "SANDBOX_VIOLATION"
        result["error"] = {"type": "SandboxViolation", "message": str(e), "traceback": traceback.format_exc(limit=3)}
        result["console"] = buf.getvalue().splitlines()
    except MemoryError:
        result["status"] = "SANDBOX_VIOLATION"
        result["error"] = {"type": "ResourceLimit", "message": "Memory limit exceeded (512 MB).", "traceback": ""}
    except Exception as e:  # noqa: BLE001 — user code errors are reported, not crashed
        result["status"] = "FAILED"
        result["error"] = {"type": type(e).__name__, "message": str(e)[:500], "traceback": traceback.format_exc(limit=6)}
        result["console"] = buf.getvalue().splitlines()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["metrics"] = {"user_cpu_sec": round(usage.ru_utime, 3), "system_cpu_sec": round(usage.ru_stime, 3), "max_rss_mb": round(usage.ru_maxrss / 1024, 2)}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, default=str)
    return 0


def _allowed_read() -> bool:
    # Reading the two sandbox-provided paths is performed with the child's
    # privileged startup context before builtins restriction applies to user code.
    return True


if __name__ == "__main__":
    sys.exit(main(sys.argv))
