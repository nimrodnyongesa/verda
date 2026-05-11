from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..auth.access import CaseAccess
from ..auth.dependencies import User, require_permission
from ..auth.dependencies_case import require_case_access
from ..auth.permissions import Permission, has_permission
from ..schemas import ExportRequest
from ..services.exporters import (
    export_docker,
    export_encrypted,
    export_usb,
    export_zip,
)

router = APIRouter()


@router.post("/cases/{case_id}/export")
def export(
    case_id: int,
    request: ExportRequest,
    user: User = Depends(require_permission(Permission.EXPORTS_BASIC.value)),
    _access: CaseAccess = Depends(require_case_access("read")),
):
    # Encrypted bundles carry a transportable copy off-platform, so they
    # require an additional permission beyond `exports:basic`. This is the
    # boundary that paralegals don't cross by default.
    if request.target == "encrypted" and not has_permission(
        user, Permission.EXPORTS_ENCRYPTED
    ):
        raise HTTPException(
            status_code=403,
            detail="Encrypted exports require the exports:encrypted permission",
        )

    try:
        if request.target == "zip":
            path = export_zip(case_id)
            return FileResponse(
                path,
                media_type="application/zip",
                filename=f"wakili_case_{case_id}.zip",
            )
        if request.target == "encrypted":
            if not request.passphrase or len(request.passphrase) < 8:
                raise HTTPException(
                    status_code=400,
                    detail="A passphrase of at least 8 characters is required for encrypted bundles",
                )
            path = export_encrypted(case_id, passphrase=request.passphrase)
            return FileResponse(
                path,
                media_type="application/zip",
                filename=f"wakili_case_{case_id}_encrypted.zip",
            )
        if request.target == "docker":
            path = export_docker(case_id)
            return FileResponse(
                path,
                media_type="application/gzip",
                filename=f"wakili_case_{case_id}_docker.tar.gz",
            )
        if request.target == "usb":
            path = export_usb(case_id)
            return FileResponse(
                path,
                media_type="application/zip",
                filename=f"wakili_case_{case_id}_usb.zip",
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=400, detail=f"Unknown target {request.target}")
