"""Deterministic demo seeding: synthetic dataset → collection → functions → correlation → report."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CollectContext
from app.collectors.event_collector import EventCollector
from app.collectors.file_collector import FileCollector
from app.collectors.network_collector import NetworkCollector
from app.collectors.process_collector import ProcessCollector
from app.collectors.user_collector import UserCollector
from app.config import get_settings
from app.core import audit
from app.db.models import (
    AiAnalysis,
    AnalysisType,
    CollectorType,
    ForensicScript,
    Investigation,
    InvestigationReport,
    Provenance,
    ReportStatus,
    SourceMode,
    TargetOS,
    User,
)
from app.services import synthetic_data
from app.services.evidence_service import store_items
from app.services.report_service import render_report
from app.services.script_service import run_script
from app.services.template_service import get_template

settings = get_settings()

DEMO_CASE_NAME = "DEMO-Corp-Breach-2026"
DEMO_DATASET = "synthetic-corp-breach"

DEMO_FQL_QUERIES = [
    "INVESTIGATE processes WHERE user = 'svc_backup'",
    "INVESTIGATE events WHERE type = 'login_failure'",
    "INVESTIGATE network WHERE dst_port = 4444",
    "INVESTIGATE files WHERE path CONTAINS 'Temp'",
    "TIMELINE FROM 2026-09-26T10:00 TO 2026-09-26T10:30",
]


async def seed_demo(db: AsyncSession, user: User) -> dict:
    dest = Path(settings.dataset_dir) / DEMO_DATASET
    synthetic_data.generate_dataset(dest)

    existing = (await db.execute(select(Investigation).where(Investigation.name == DEMO_CASE_NAME))).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()

    inv = Investigation(
        name=DEMO_CASE_NAME,
        description="Deterministic SYNTHETIC demonstration case: phishing → encoded PowerShell → dropper → persistence → C2 → exfiltration. All evidence is generated sample data.",
        target_host="workstation-07.demo.lab",
        target_os=TargetOS.WINDOWS.value,
        source_mode=SourceMode.DATASET.value,
        source_path=DEMO_DATASET,
        provenance=Provenance.SYNTHETIC.value,
        created_by=user.id,
        lead_investigator=user.id,
    )
    db.add(inv)
    await db.flush()

    ctx_base = {"investigation": inv, "rules": {}, "provenance": Provenance.SYNTHETIC, "deadline": datetime.now(UTC).timestamp() + 60}
    collected = {}
    for ctype, cls in (
        (CollectorType.PROCESS, ProcessCollector),
        (CollectorType.FILE, FileCollector),
        (CollectorType.NETWORK, NetworkCollector),
        (CollectorType.USER, UserCollector),
        (CollectorType.EVENT, EventCollector),
    ):
        ctx = CollectContext(**ctx_base)
        items = await cls().collect(ctx)
        stored, _ = await store_items(db, inv, None, ctype, items, user, Provenance.SYNTHETIC)
        collected[ctype.value] = stored
    await db.commit()

    scripts_run = []
    for tpl_id in ("process-analysis", "windows-event-analysis", "network-artifact-analysis", "hash-verification"):
        tpl = get_template(tpl_id)
        script = ForensicScript(
            investigation_id=inv.id,
            name=f"demo-{tpl_id}",
            description=f"Seeded demo function from template '{tpl['title']}'.",
            template_id=tpl_id,
            code=tpl["code"],
            created_by=user.id,
        )
        db.add(script)
        await db.flush()
        execution = await run_script(db, inv, script.id, tpl["code"], user)
        scripts_run.append({"script": script.name, "status": execution.status, "findings": execution.findings_count})

    from app.ai import heuristic
    from app.db.models import EvidenceItem

    items = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == inv.id))).scalars().all()
    result = heuristic.correlate(list(items))
    analysis = AiAnalysis(
        investigation_id=inv.id,
        analysis_type=AnalysisType.CORRELATION.value,
        engine="HEURISTIC",
        model_used="forgex-correlation-engine-v1",
        input_evidence_ids=sorted({i for e in result["attack_stages"] + result["suspicious_indicators"] + result["mitre_techniques"] for i in e["evidence_ids"]}),
        result=result,
        confidence_score=result["confidence"],
        created_by=user.id,
    )
    db.add(analysis)
    await db.flush()

    report = InvestigationReport(
        investigation_id=inv.id,
        title=f"{DEMO_CASE_NAME} — full report",
        report_type="FULL",
        status=ReportStatus.GENERATING.value,
        created_by=user.id,
    )
    db.add(report)
    await db.flush()
    path = await render_report(db, report)
    report.status = ReportStatus.READY.value
    report.file_path = str(path)
    report.file_size_bytes = path.stat().st_size
    report.completed_at = datetime.now(UTC)

    await audit.audit(db, "DEMO_SEEDED", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"collected": collected, "scripts": scripts_run})
    await db.commit()
    return {
        "investigation_id": inv.id,
        "case": DEMO_CASE_NAME,
        "provenance": "SYNTHETIC",
        "collected": collected,
        "scripts": scripts_run,
        "correlation_confidence": result["confidence"],
        "report_id": report.id,
        "demo_fql_queries": DEMO_FQL_QUERIES,
        "dataset_stats": synthetic_data.dataset_stats(dest),
    }
