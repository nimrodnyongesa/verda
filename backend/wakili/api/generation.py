from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.access import CaseAccess
from ..auth.dependencies import User, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import Permission
from ..services.orchestrator import latest_run, list_events, list_runs, run_generation

router = APIRouter()


@router.post("/cases/{case_id}/generate")
def generate(
    case_id: int,
    _user: User = Depends(require_permission(Permission.GENERATION_RUN.value)),
    _access: CaseAccess = Depends(require_case_access("write")),
) -> dict:
    try:
        result = run_generation(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/cases/{case_id}/runs")
def runs(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    return {"runs": list_runs(case_id)}


@router.get("/cases/{case_id}/runs/latest")
def latest(
    case_id: int,
    _user: User = Depends(require_permission(Permission.CASES_READ.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
) -> dict:
    run = latest_run(case_id)
    if not run:
        raise HTTPException(status_code=404, detail="No runs yet")
    return {"run": run, "events": list_events(run["id"])}


@router.get("/runs/{run_id}/events")
def events(run_id: int, _: User = Depends(require_permission(Permission.CASES_READ.value))) -> dict:
    return {"events": list_events(run_id)}
