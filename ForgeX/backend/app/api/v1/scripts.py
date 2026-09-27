"""Script Lab endpoints: templates, script CRUD + versions, validate, run, stop, executions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser, require_min_role
from app.core.errors import NotFound, ValidationError
from app.db.models import Finding, ForensicScript, Role, ScriptExecution, ScriptVersion, User
from app.db.session import get_db
from app.execution.validation import validate_function
from app.schemas.requests import RunScriptRequest, ScriptCreate, ScriptUpdate, ValidateCodeRequest
from app.services import investigation_service, script_service, template_service

router = APIRouter(tags=["script-lab"])


@router.get("/templates")
async def templates(user: CurrentUser):
    return {"templates": [dict(t) for t in template_service.list_templates()]}


@router.get("/investigations/{inv_id}/scripts")
async def list_scripts(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    rows = (await db.execute(select(ForensicScript).where(ForensicScript.investigation_id == inv_id).order_by(ForensicScript.updated_at.desc()))).scalars().all()
    return {"data": [_script_dict(s) for s in rows]}


@router.post("/investigations/{inv_id}/scripts", status_code=201)
async def create_script(inv_id: str, body: ScriptCreate, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    code = body.code
    template_id = body.template_id
    if code is None:
        tpl = template_service.get_template(template_id or "custom-function")
        if not tpl:
            raise NotFound(f"No template '{template_id}'")
        code = tpl["code"]
    if body.language == "PYFUNC":
        validate_function(code)
    script = ForensicScript(
        investigation_id=inv_id,
        name=body.name,
        description=body.description,
        language=body.language,
        template_id=template_id,
        code=code,
        version=1,
        created_by=user.id,
    )
    db.add(script)
    await db.flush()
    db.add(ScriptVersion(script_id=script.id, version=1, code=code, note="initial"))
    await audit.audit(db, "SCRIPT_CREATED", actor=user, resource_type="forensic_script", resource_id=script.id, metadata={"template": template_id}, request=request)
    await db.commit()
    return _script_dict(script)


@router.get("/scripts/{script_id}")
async def get_script(script_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    script = await db.get(ForensicScript, script_id)
    if not script:
        raise NotFound(f"No script {script_id}")
    await investigation_service.get_for_user(db, script.investigation_id, user)
    return _script_dict(script)


@router.put("/scripts/{script_id}")
async def update_script(script_id: str, body: ScriptUpdate, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    script = await db.get(ForensicScript, script_id)
    if not script:
        raise NotFound(f"No script {script_id}")
    await investigation_service.get_for_user(db, script.investigation_id, user)
    if script.language == "PYFUNC":
        validate_function(body.code)
    script.code = body.code
    if body.bump_version:
        script.version += 1
        db.add(ScriptVersion(script_id=script.id, version=script.version, code=body.code, note=body.note))
    await audit.audit(db, "SCRIPT_UPDATED", actor=user, resource_type="forensic_script", resource_id=script.id, metadata={"version": script.version}, request=request)
    await db.commit()
    return _script_dict(script)


@router.get("/scripts/{script_id}/versions")
async def script_versions(script_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    script = await db.get(ForensicScript, script_id)
    if not script:
        raise NotFound(f"No script {script_id}")
    await investigation_service.get_for_user(db, script.investigation_id, user)
    rows = (await db.execute(select(ScriptVersion).where(ScriptVersion.script_id == script_id).order_by(ScriptVersion.version.desc()))).scalars().all()
    return {"data": [{"version": v.version, "note": v.note, "created_at": v.created_at.isoformat() if v.created_at else None, "code": v.code} for v in rows]}


@router.post("/scripts/validate")
async def validate_code(body: ValidateCodeRequest, user: User = Depends(require_min_role(Role.INVESTIGATOR))):
    return validate_function(body.code)


@router.post("/scripts/{script_id}/run", status_code=202)
async def run_script(script_id: str, body: RunScriptRequest, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    script = await db.get(ForensicScript, script_id)
    if not script:
        raise NotFound(f"No script {script_id}")
    inv = await investigation_service.get_for_user(db, body.investigation_id, user)
    code = body.code or script.code
    if script.language != "PYFUNC":
        raise ValidationError("Only PYFUNC forensic functions can run in the Script Lab sandbox. FQL scripts run via the FQL console.")
    execution = await script_service.run_script(db, inv, script.id, code, user, request)
    return {"execution_id": execution.id, "status": execution.status, "findings": execution.findings_count, "error": execution.error_message}


@router.post("/investigations/{inv_id}/run-adhoc", status_code=202)
async def run_adhoc(inv_id: str, body: RunScriptRequest, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    """Run unsaved code directly (Script Lab 'Run' without saving)."""
    inv = await investigation_service.get_for_user(db, inv_id, user)
    if not body.code:
        raise ValidationError("code is required for ad-hoc execution.")
    execution = await script_service.run_script(db, inv, None, body.code, user, request)
    return {"execution_id": execution.id, "status": execution.status, "findings": execution.findings_count, "error": execution.error_message}


@router.post("/executions/{execution_id}/stop")
async def stop_execution(execution_id: str, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    stopped = await script_service.stop_script(db, execution_id, user, request)
    return {"stopped": stopped}


@router.get("/investigations/{inv_id}/executions")
async def list_executions(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    rows = (await db.execute(select(ScriptExecution).where(ScriptExecution.investigation_id == inv_id).order_by(ScriptExecution.started_at.desc()).limit(100))).scalars().all()
    return {"data": [_exec_dict(e) for e in rows]}


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    ex = await db.get(ScriptExecution, execution_id)
    if not ex:
        raise NotFound(f"No execution {execution_id}")
    await investigation_service.get_for_user(db, ex.investigation_id, user)
    findings = (await db.execute(select(Finding).where(Finding.execution_id == execution_id))).scalars().all()
    return {**_exec_dict(ex), "findings": [_finding_dict(f) for f in findings]}


def _script_dict(s: ForensicScript) -> dict:
    return {
        "id": s.id, "investigation_id": s.investigation_id, "name": s.name, "description": s.description,
        "language": s.language, "template_id": s.template_id, "code": s.code, "version": s.version,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _exec_dict(e: ScriptExecution) -> dict:
    return {
        "id": e.id, "script_id": e.script_id, "investigation_id": e.investigation_id, "status": e.status,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        "console_log": e.console_log, "findings_count": e.findings_count,
        "resource_usage": e.resource_usage, "error_message": e.error_message,
    }


def _finding_dict(f: Finding) -> dict:
    return {
        "id": f.id, "investigation_id": f.investigation_id, "execution_id": f.execution_id,
        "analysis_id": f.analysis_id, "source": f.source, "severity": f.severity, "title": f.title,
        "description": f.description, "evidence_ids": f.evidence_ids, "mitre_techniques": f.mitre_techniques,
        "status": f.status, "created_at": f.created_at.isoformat() if f.created_at else None,
    }
