"""Investigation report generation → PDF (reportlab)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select

from app.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    AiAnalysis,
    AuditLog,
    EvidenceItem,
    Finding,
    Investigation,
    InvestigationReport,
    Job,
    JobStatus,
    ReportStatus,
    User,
)
from app.services import blockchain_service
from app.services.timeline_service import build_timeline

log = get_logger("report")
settings = get_settings()

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("FH1", parent=_styles["Title"], fontSize=20, textColor=colors.HexColor("#0b3d5c"))
H2 = ParagraphStyle("FH2", parent=_styles["Heading2"], textColor=colors.HexColor("#0b3d5c"))
SMALL = ParagraphStyle("FSmall", parent=_styles["BodyText"], fontSize=8, leading=10)
MONO = ParagraphStyle("FMono", parent=_styles["Code"], fontSize=7, leading=9)


def _table(rows, widths=None, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3d5c")) if header else ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
            ]
        )
    )
    return t


async def render_report(db, report: InvestigationReport) -> Path:
    investigation = await db.get(Investigation, report.investigation_id)
    evidence = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == investigation.id))).scalars().all()
    findings = (await db.execute(select(Finding).where(Finding.investigation_id == investigation.id).order_by(Finding.created_at))).scalars().all()
    analyses = (await db.execute(select(AiAnalysis).where(AiAnalysis.investigation_id == investigation.id).order_by(AiAnalysis.created_at.desc()))).scalars().all()
    timeline = await build_timeline(db, investigation.id)
    chain = await blockchain_service.verify_chain(db)
    audit_rows = (await db.execute(select(AuditLog).where(AuditLog.resource_id == investigation.id).order_by(AuditLog.created_at).limit(50))).scalars().all()
    author = await db.get(User, report.created_by)

    out_dir = Path(settings.file_store_dir) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.id}.pdf"

    story = []
    story.append(Paragraph("FORGE-X Investigation Report", H1))
    story.append(Paragraph(report.title or investigation.name, _styles["Heading3"]))
    story.append(Spacer(1, 6 * mm))
    meta = [
        ["Case", investigation.name, "Status", investigation.status],
        ["Target", f"{investigation.target_host} ({investigation.target_os})", "Source mode", investigation.source_mode],
        ["Provenance", investigation.provenance, "Generated", datetime.now(UTC).isoformat()],
        ["Report type", report.report_type, "Author", author.username if author else "-"],
        ["Evidence items", str(len(evidence)), "Findings", str(len(findings))],
    ]
    story.append(_table(meta, widths=[30 * mm, 60 * mm, 30 * mm, 50 * mm], header=False))
    story.append(Spacer(1, 6 * mm))
    if investigation.provenance == "SYNTHETIC":
        story.append(Paragraph("<b>NOTE:</b> This case was generated from SYNTHETIC sample data for demonstration. It is not real-world evidence.", SMALL))
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Evidence Summary", H2))
    by_type: dict[str, int] = {}
    for e in evidence:
        by_type[e.evidence_type] = by_type.get(e.evidence_type, 0) + 1
    rows = [["Type", "Count"]] + [[k, str(v)] for k, v in sorted(by_type.items())]
    story.append(_table(rows, widths=[70 * mm, 30 * mm]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Evidence integrity (SHA-256 anchor chain): " + ("VALID" if chain["valid"] else f"BROKEN at record {chain['broken_at_record_id']}"), SMALL))
    story.append(Paragraph(f"{chain['records']} anchor records · {chain['chain']}", SMALL))

    story.append(Paragraph("2. Findings", H2))
    if findings:
        rows = [["Severity", "Title", "Source", "Status", "Evidence refs"]]
        for f in findings:
            rows.append([f.severity, Paragraph(f.title, SMALL), f.source, f.status, ", ".join(i[:8] for i in f.evidence_ids[:4])])
        story.append(_table(rows, widths=[20 * mm, 75 * mm, 18 * mm, 20 * mm, 37 * mm]))
    else:
        story.append(Paragraph("No findings recorded.", SMALL))

    story.append(Paragraph("3. AI Incident Reconstruction", H2))
    corr = next((a for a in analyses if a.analysis_type == "CORRELATION"), None)
    if corr:
        res = corr.result or {}
        story.append(Paragraph(f"Engine: {corr.engine} · Model: {corr.model_used} · Confidence: {corr.confidence_score}", SMALL))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("<b>What happened:</b> " + str(res.get("what_happened", "")), SMALL))
        stages = res.get("attack_stages", [])
        if stages:
            story.append(Spacer(1, 2 * mm))
            story.append(ListFlowable([ListItem(Paragraph(f"<b>{s.get('stage')}</b>: {s.get('description')} <i>(evidence: {', '.join(i[:8] for i in s.get('evidence_ids', []))})</i>", SMALL)) for s in stages], bulletType="bullet"))
        mitre = res.get("mitre_techniques", [])
        if mitre:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("MITRE ATT&amp;CK mapping: " + ", ".join(f"{m.get('technique_id')} ({m.get('name')})" for m in mitre), SMALL))
        gaps = res.get("gaps", [])
        if gaps:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("Analysis gaps: " + "; ".join(gaps), SMALL))
    else:
        story.append(Paragraph("No AI correlation has been run for this case.", SMALL))

    story.append(PageBreak())
    story.append(Paragraph("4. Investigation Timeline (first 120 entries)", H2))
    rows = [["Timestamp", "Type", "Severity", "Description"]]
    for entry in timeline[:120]:
        rows.append([entry["timestamp"][:19], entry["type"], entry["severity"], Paragraph(entry["label"][:160], SMALL)])
    story.append(_table(rows, widths=[32 * mm, 30 * mm, 18 * mm, 90 * mm]))

    if report.report_type in ("FULL", "CHAIN_OF_CUSTODY"):
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("5. Chain of Custody / Audit", H2))
        rows = [["When", "Actor", "Action", "Result"]]
        for a in audit_rows:
            rows.append([a.created_at.isoformat()[:19] if a.created_at else "", a.actor_email or "-", a.action, a.result])
        story.append(_table(rows, widths=[34 * mm, 45 * mm, 60 * mm, 20 * mm]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Evidence hashes (first 40):", SMALL))
        for e in evidence[:40]:
            story.append(Paragraph(f"{e.id[:8]}… {e.evidence_type:20s} sha256:{e.data_hash}", MONO))

    doc = SimpleDocTemplate(str(path), pagesize=A4, title=report.title or investigation.name, author="ForgeX")
    doc.build(story)
    return path


async def run_report_job(db, job: Job) -> None:

    report_id = (job.payload or {}).get("report_id")
    report = await db.get(InvestigationReport, report_id)
    if not report:
        job.status = JobStatus.FAILED.value
        job.error_message = "Report record missing"
        return
    try:
        path = await render_report(db, report)
        report.status = ReportStatus.READY.value
        report.file_path = str(path)
        report.file_size_bytes = path.stat().st_size
        report.completed_at = datetime.now(UTC)
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.now(UTC)
        job.result = {"report_id": report.id, "size": report.file_size_bytes}
    except Exception as e:  # noqa: BLE001
        log.exception("report_failed", report=report_id, error=str(e)[:200])
        report.status = ReportStatus.FAILED.value
        job.status = JobStatus.FAILED.value
        job.error_message = f"{type(e).__name__}: {str(e)[:300]}"
    from app.core.websocket import manager

    await manager.broadcast(job.investigation_id, {"type": "REPORT_READY", "report_id": report.id, "status": report.status})
