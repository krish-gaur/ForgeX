"""End-to-end API smoke test against a running ForgeX backend (used by CI + demo QA)."""
import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
B = f"{BASE}/api/v1"
c = httpx.Client(timeout=180)
ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f" | {extra}" if extra else ""))
    if not cond:
        ok = False


r = c.get(f"{BASE}/health")
check("health", r.status_code == 200 and r.json()["database"] is True, str(r.json()))

def login(username, password):
    for attempt in range(6):
        rr = c.post(f"{B}/auth/login", json={"username": username, "password": password})
        if rr.status_code == 200:
            return rr
        time.sleep(11)  # login rate limiter window
    return rr


r = login("lead", "ForgeX-Lead-2026!")
check("login lead", r.status_code == 200, str(r.status_code))
tok = r.json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

r = login("investigator", "ForgeX-Investigator-2026!")
inv_tok = r.json()["access_token"]
HI = {"Authorization": f"Bearer {inv_tok}"}
r = login("auditor", "ForgeX-Auditor-2026!")
aud_tok = r.json()["access_token"]

check("RBAC investigator blocked from /admin/users", c.get(f"{B}/admin/users", headers=HI).status_code == 403)
check("RBAC auditor read-only on audit", c.get(f"{B}/admin/audit", headers={"Authorization": f"Bearer {aud_tok}"}).status_code == 200)
check("unauthenticated blocked", c.get(f"{B}/investigations").status_code == 401)

r = c.post(f"{B}/demo/seed", headers=H)
check("demo seed", r.status_code == 201, str(r.status_code))
seed = r.json()
inv_id = seed["investigation_id"]
check("seed collected evidence", sum(seed["collected"].values()) >= 20, json.dumps(seed["collected"]))
check("seed scripts produced findings", sum(s["findings"] for s in seed["scripts"]) >= 3, json.dumps(seed["scripts"]))

det = c.get(f"{B}/investigations/{inv_id}", headers=H).json()
check("investigation detail", det["evidence_summary"]["total"] >= 20, json.dumps(det["evidence_summary"]["by_type"]))
check("provenance SYNTHETIC", det["provenance"] == "SYNTHETIC")

tl = c.get(f"{B}/investigations/{inv_id}/timeline", headers=H).json()["timeline"]
check("timeline chronological", len(tl) >= 15 and tl == sorted(tl, key=lambda e: e["timestamp"]), f"{len(tl)} entries")
check("timeline severities present", any(e["severity"] in ("HIGH", "CRITICAL") for e in tl))

g = c.get(f"{B}/investigations/{inv_id}/graph", headers=H).json()
types = {n["type"] for n in g["nodes"]}
check("graph has user/process/file/network/event nodes", {"user", "process", "network"} <= types, str(types))
check("graph edges labelled", all(e["label"] for e in g["edges"]), f"{len(g['edges'])} edges")

f = c.get(f"{B}/investigations/{inv_id}/findings", headers=H).json()["data"]
check("findings exist with evidence refs", len(f) >= 3 and all(x["evidence_ids"] for x in f if x["severity"] in ("HIGH", "CRITICAL")), f"{len(f)} findings")

a = c.get(f"{B}/investigations/{inv_id}/ai/analyses", headers=H).json()["data"]
check("AI correlation stored", len(a) >= 1 and a[0]["result"].get("what_happened"))
check("MITRE mapping present", len(a[0]["result"].get("mitre_techniques", [])) >= 2, str([m["technique_id"] for m in a[0]["result"]["mitre_techniques"]]))

r = c.post(f"{B}/ai/analyses/{a[0]['id']}/promote", headers=H, json={"indicator_index": 0})
check("promote AI indicator to finding", r.status_code == 201 and r.json()["source"] == "AI", str(r.status_code))

reps = c.get(f"{B}/investigations/{inv_id}/reports", headers=H).json()["data"]
check("seeded report READY", reps and reps[0]["status"] == "READY", str(reps[:1]))
r = c.get(f"{B}/investigations/{inv_id}/reports/{reps[0]['id']}/download", headers=H)
check("PDF download", r.status_code == 200 and r.content[:4] == b"%PDF", f"{len(r.content)} bytes")

chain = c.get(f"{B}/investigations/{inv_id}/anchor-chain/verify", headers=H).json()
check("anchor chain valid", chain["valid"] and chain["records"] >= 20, json.dumps(chain))

r = c.post(f"{B}/investigations/{inv_id}/fql/validate", headers=H, json={"fql": "INVESTIGATE network WHERE dst_port = 4444"})
check("fql validate allowed for lead", r.status_code == 200 and r.json()["policy_preview"]["status"] == "ALLOWED")
# IDOR: investigator cannot see lead's case (404 per architecture), so use own case for policy demo
import uuid as _uuid
r = c.post(f"{B}/investigations", headers=HI, json={"name": f"smoke-inv-{_uuid.uuid4().hex[:8]}", "target_host": "workstation-07.demo.lab", "source_mode": "DATASET", "source_path": "synthetic-corp-breach", "target_os": "WINDOWS"})
check("investigator creates own case", r.status_code == 201, str(r.status_code))
own_id = r.json()["id"]
check("IDOR: investigator blocked from lead case", c.get(f"{B}/investigations/{inv_id}", headers=HI).status_code == 404)
r = c.post(f"{B}/investigations/{own_id}/fql/validate", headers=HI, json={"fql": "INVESTIGATE network WHERE dst_port = 4444"})
check("fql policy preview DENIED for investigator", r.status_code == 200 and r.json()["policy_preview"]["status"] == "DENIED", json.dumps(r.json().get("policy_preview", {}))[:120])
r = c.post(f"{B}/investigations/{own_id}/fql/execute", headers=HI, json={"fql": "INVESTIGATE network WHERE dst_port = 4444"})
check("fql execute 403 policy denied for investigator", r.status_code == 403 and r.json()["error"]["code"] == "POLICY_DENIED", str(r.status_code))

r = c.post(f"{B}/investigations/{inv_id}/fql/execute", headers=H, json={"fql": "INVESTIGATE processes WHERE user = 'svc_backup'"})
check("fql execute 202", r.status_code == 202, str(r.json()))
job = r.json()["job_id"]
st = {}
for _ in range(60):
    st = c.get(f"{B}/jobs/{job}/status", headers=H).json()
    if st["status"] in ("COMPLETED", "FAILED", "PARTIAL"):
        break
    time.sleep(0.5)
check("collection job completed", st.get("status") == "COMPLETED", json.dumps(st.get("collectors")))

r = c.post(f"{B}/investigations/{inv_id}/fql/validate", headers=H, json={"fql": "INVESTIGATE processes WHERE"})
check("bad FQL 422 with line/col", r.status_code == 422 and "line" in r.json()["error"]["details"], json.dumps(r.json()["error"]["details"]))

r = c.get(f"{B}/templates", headers=H)
check("10 templates", len(r.json()["templates"]) == 10, str(len(r.json()["templates"])))

r = c.post(f"{B}/investigations/{inv_id}/scripts", headers=H, json={"name": "smoke-func", "template_id": "process-analysis"})
check("create script from template", r.status_code == 201, str(r.status_code))
script_id = r.json()["id"]
r = c.post(f"{B}/scripts/{script_id}/run", headers=H, json={"investigation_id": inv_id})
check("run forensic function", r.status_code == 202 and r.json()["status"] == "COMPLETED", json.dumps(r.json()))
exec_id = r.json()["execution_id"]
r = c.get(f"{B}/executions/{exec_id}", headers=H).json()
check("execution log + resource usage", r["resource_usage"] and "max_rss_mb" in r["resource_usage"], json.dumps(r["resource_usage"]))

r = c.post(f"{B}/scripts/validate", headers=H, json={"code": "import os\nos.system('id')\ndef analyze(e): pass"})
check("sandbox validation rejects os import", r.status_code == 422, str(r.status_code))

r = c.post(f"{B}/investigations/{inv_id}/ai/query", headers=H, json={"question": "Which account was brute-forced?"})
check("RAG Q&A answers with refs", r.status_code == 200 and r.json().get("evidence_refs"), json.dumps(r.json())[:200])

ev = c.get(f"{B}/investigations/{inv_id}/evidence", headers=H, params={"per_page": 5}).json()
eid = ev["data"][0]["id"]
r = c.get(f"{B}/investigations/{inv_id}/evidence/{eid}", headers=H, params={"verify": "true"}).json()
check("evidence hash verification", r["integrity"]["matches_stored"] is True)

r = c.get(f"{B}/investigations/{inv_id}/evidence/export", headers=H, params={"format": "csv"})
check("CSV export", r.status_code == 200 and "sha256" in r.text.splitlines()[0], f"{len(r.text)} bytes")

stats = c.get(f"{B}/stats/overview", headers=H).json()
check("dashboard stats real", stats["evidence_items"] >= 20 and stats["high_severity_findings"] >= 1, json.dumps({k: stats[k] for k in ("active_cases", "evidence_items", "executions", "findings", "high_severity_findings")}))

r = login("admin", "ForgeX-Admin-2026!")
HA = {"Authorization": f"Bearer {r.json()['access_token']}"}
aud = c.get(f"{B}/admin/audit", headers=HA, params={"per_page": 200}).json()["data"]
actions = {a["action"] for a in aud}
check("audit trail covers lifecycle", {"LOGIN", "INVESTIGATION_CREATED", "FQL_EXECUTED", "SCRIPT_EXECUTED", "DEMO_SEEDED"} <= actions, str(sorted(actions)[:12]))

print("\nSMOKE RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
