"""Integration + E2E: login → case → evidence → template → edit → validate → execute → findings → report."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import synthetic_data
from tests.conftest import auth, login

settings = get_settings()


@pytest.fixture(scope="module", autouse=True)
def dataset():
    dest = Path(settings.dataset_dir) / "synthetic-corp-breach"
    synthetic_data.generate_dataset(dest)
    return dest


async def _wait_job(client, headers, job_id, tries=60):
    for _ in range(tries):
        r = await client.get(f"/api/v1/jobs/{job_id}/status", headers=headers)
        st = r.json()
        if st["status"] in ("COMPLETED", "FAILED", "PARTIAL"):
            return st
        await asyncio.sleep(0.4)
    return st


async def test_full_investigation_journey(client, users, policy):
    token = await login(client, "lead")
    h = auth(token)

    # 1. create case
    r = await client.post(
        "/api/v1/investigations",
        headers=h,
        json={"name": "e2e-case", "target_host": "ws-01.lab", "target_os": "WINDOWS", "source_mode": "DATASET", "source_path": "synthetic-corp-breach"},
    )
    assert r.status_code == 201, r.text
    inv = r.json()["id"]

    # duplicate name → 409
    r2 = await client.post("/api/v1/investigations", headers=h, json={"name": "e2e-case", "target_host": "ws-01.lab"})
    assert r2.status_code == 409

    # 2. FQL validate (syntax + policy preview)
    r = await client.post(f"/api/v1/investigations/{inv}/fql/validate", headers=h, json={"fql": "INVESTIGATE processes WHERE user = 'svc_backup'"})
    assert r.status_code == 200 and r.json()["valid"] is True
    assert r.json()["policy_preview"]["status"] == "ALLOWED"

    # 3. execute → job → evidence
    r = await client.post(f"/api/v1/investigations/{inv}/fql/execute", headers=h, json={"fql": "INVESTIGATE processes WHERE user = 'svc_backup'"})
    assert r.status_code == 202
    st = await _wait_job(client, h, r.json()["job_id"])
    assert st["status"] == "COMPLETED" and st["items_collected_so_far"] >= 1

    # collect everything for downstream screens
    r = await client.post(f"/api/v1/investigations/{inv}/fql/execute", headers=h, json={"fql": "INVESTIGATE events\nINVESTIGATE network\nINVESTIGATE files\nINVESTIGATE users"})
    st = await _wait_job(client, h, r.json()["job_id"])
    assert st["status"] == "COMPLETED"

    # 4. evidence list + integrity verify + export
    r = await client.get(f"/api/v1/investigations/{inv}/evidence", headers=h, params={"per_page": 100})
    ev = r.json()["data"]
    assert len(ev) >= 20
    r = await client.get(f"/api/v1/investigations/{inv}/evidence/{ev[0]['id']}", headers=h, params={"verify": "true"})
    assert r.json()["integrity"]["matches_stored"] is True
    r = await client.get(f"/api/v1/investigations/{inv}/evidence/export", headers=h, params={"format": "csv"})
    assert r.status_code == 200 and r.text.startswith("id,type,collected_at,sha256,data")

    # 5. template → script → edit → validate → run
    r = await client.get("/api/v1/templates", headers=h)
    tpls = {t["id"]: t for t in r.json()["templates"]}
    assert len(tpls) == 10
    code = tpls["process-analysis"]["code"]
    assert "def analyze(evidence)" in code
    r = await client.post(f"/api/v1/investigations/{inv}/scripts", headers=h, json={"name": "e2e-func", "template_id": "process-analysis"})
    assert r.status_code == 201
    script = r.json()["id"]
    edited = code.replace("Reviewed", "Reviewed(e2e)")
    r = await client.put(f"/api/v1/scripts/{script}", headers=h, json={"code": edited, "note": "e2e edit"})
    assert r.status_code == 200 and r.json()["version"] == 2
    r = await client.post("/api/v1/scripts/validate", headers=h, json={"code": edited})
    assert r.status_code == 200
    r = await client.post(f"/api/v1/scripts/{script}/run", headers=h, json={"investigation_id": inv})
    assert r.status_code == 202 and r.json()["status"] == "COMPLETED"
    assert r.json()["findings"] >= 2

    # 6. findings list + verify workflow
    r = await client.get(f"/api/v1/investigations/{inv}/findings", headers=h)
    findings = r.json()["data"]
    assert findings and all(f["evidence_ids"] for f in findings if f["severity"] in ("HIGH", "CRITICAL"))
    r = await client.patch(f"/api/v1/findings/{findings[0]['id']}", headers=h, json={"status": "VERIFIED"})
    assert r.json()["status"] == "VERIFIED"

    # 7. timeline + graph
    r = await client.get(f"/api/v1/investigations/{inv}/timeline", headers=h)
    assert len(r.json()["timeline"]) >= 10
    r = await client.get(f"/api/v1/investigations/{inv}/graph", headers=h)
    assert r.json()["nodes"] and r.json()["edges"]

    # 8. AI correlate → analyses → promote
    r = await client.post(f"/api/v1/investigations/{inv}/ai/correlate", headers=h)
    assert r.status_code == 202
    analyses = []
    for _ in range(60):
        await asyncio.sleep(0.4)
        analyses = (await client.get(f"/api/v1/investigations/{inv}/ai/analyses", headers=h)).json()["data"]
        if analyses:
            break
    assert analyses and analyses[0]["result"]["what_happened"]
    r = await client.post(f"/api/v1/ai/analyses/{analyses[0]['id']}/promote", headers=h, json={"indicator_index": 0})
    assert r.status_code == 201 and r.json()["source"] == "AI"

    # 9. RAG Q&A
    r = await client.post(f"/api/v1/investigations/{inv}/ai/query", headers=h, json={"question": "which process executed an encoded command?"})
    assert r.status_code == 200 and r.json()["evidence_refs"]

    # 10. report → download
    r = await client.post(f"/api/v1/investigations/{inv}/reports", headers=h, json={"type": "FULL", "title": "e2e report"})
    assert r.status_code == 202
    report_id = r.json()["report_id"]
    ready = False
    for _ in range(60):
        await asyncio.sleep(0.4)
        reps = (await client.get(f"/api/v1/investigations/{inv}/reports", headers=h)).json()["data"]
        if reps and reps[0]["status"] == "READY":
            ready = True
            break
    assert ready
    r = await client.get(f"/api/v1/investigations/{inv}/reports/{report_id}/download", headers=h)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # 11. audit trail recorded the journey
    r = await client.get("/api/v1/admin/audit", headers=auth(await login(client, "auditor")), params={"per_page": 200})
    actions = {a["action"] for a in r.json()["data"]}
    assert {"INVESTIGATION_CREATED", "FQL_EXECUTED", "SCRIPT_EXECUTED", "REPORT_REQUESTED"} <= actions


async def test_rbac_endpoint_matrix(client, users, policy):
    inv_token = await login(client, "investigator")
    aud_token = await login(client, "auditor")
    lead_token = await login(client, "lead")

    r = await client.post("/api/v1/investigations", headers=auth(aud_token), json={"name": "aud-case", "target_host": "10.1.1.1"})
    assert r.status_code == 403  # auditor cannot create cases

    r = await client.post("/api/v1/investigations", headers=auth(inv_token), json={"name": "inv-case", "target_host": "10.1.1.2"})
    assert r.status_code == 201
    own = r.json()["id"]

    r = await client.post(f"/api/v1/investigations/{own}/fql/execute", headers=auth(inv_token), json={"fql": "INVESTIGATE network"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "POLICY_DENIED"

    r = await client.get("/api/v1/admin/users", headers=auth(lead_token))
    assert r.status_code == 403
    r = await client.get("/api/v1/admin/users", headers=auth(await login(client, "admin")))
    assert r.status_code == 200

    r = await client.get("/api/v1/admin/audit", headers=auth(inv_token))
    assert r.status_code == 403


async def test_error_format_standard(client, users, policy):
    r = await client.get("/api/v1/investigations/does-not-exist", headers=auth(await login(client, "lead")))
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]


async def test_security_headers_present(client, users, policy):
    r = await client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]


async def test_login_rate_limited(client, users, policy):
    for _ in range(10):
        await client.post("/api/v1/auth/login", json={"username": "lead", "password": "wrong-password"})
    r = await client.post("/api/v1/auth/login", json={"username": "lead", "password": "Passw0rd!-test"})
    assert r.status_code == 429
