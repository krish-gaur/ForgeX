"""Static validation of ForgeX forensic functions before they reach the sandbox."""
from __future__ import annotations

import ast

from app.core.errors import ScriptValidationError

ALLOWED_IMPORTS = {"forgex", "json", "re", "datetime", "collections", "math", "statistics", "hashlib", "itertools", "functools", "typing", "enum", "string", "operator"}
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals", "vars"}
FORBIDDEN_ATTRS = {"__subclasses__", "__globals__", "__builtins__", "__class__", "__bases__", "__mro__", "__code__", "__import__"}
MAX_CODE_BYTES = 100_000


def validate_function(code: str) -> dict:
    problems: list[str] = []
    if not code or not code.strip():
        raise ScriptValidationError("Forensic function is empty.", details={"problems": ["empty code"]})
    if len(code.encode()) > MAX_CODE_BYTES:
        raise ScriptValidationError(f"Forensic function exceeds {MAX_CODE_BYTES} bytes.", details={"problems": ["too large"]})
    try:
        tree = ast.parse(code, filename="<forgex-function>")
    except SyntaxError as e:
        raise ScriptValidationError(
            f"Syntax error at line {e.lineno}, col {e.offset}: {e.msg}",
            details={"problems": [f"syntax: line {e.lineno}: {e.msg}"], "line": e.lineno, "col": e.offset},
        ) from e

    imports: list[str] = []
    defined: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "").split(".")[0])
        elif isinstance(node, ast.FunctionDef):
            defined.append(node.name)
        elif isinstance(node, ast.Call):
            fname = node.func
            if isinstance(fname, ast.Name) and fname.id in FORBIDDEN_CALLS:
                problems.append(f"line {node.lineno}: call to '{fname.id}' is not permitted in the sandbox")
            if isinstance(fname, ast.Attribute) and fname.attr in FORBIDDEN_ATTRS:
                problems.append(f"line {node.lineno}: access to '{fname.attr}' is not permitted")
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                problems.append(f"line {node.lineno}: access to '{node.attr}' is not permitted")

    bad_imports = sorted({i for i in imports if i and i not in ALLOWED_IMPORTS})
    for bi in bad_imports:
        problems.append(f"import of '{bi}' is not permitted (allow-list: {sorted(ALLOWED_IMPORTS)})")

    entry = None
    if "analyze" in defined or "main" in defined:
        entry = "analyze" if "analyze" in defined else "main"
    else:
        cand = [d for d in defined if d.startswith("analyze_")]
        entry = cand[0] if cand else None
    if entry is None:
        problems.append("no entry point: define `def analyze(evidence):` (or `main(evidence)`)")

    if problems:
        raise ScriptValidationError(
            "Forensic function failed validation: " + "; ".join(problems[:6]),
            details={"problems": problems},
        )
    return {"valid": True, "entry": entry, "imports": sorted({i for i in imports if i}), "functions": defined}
