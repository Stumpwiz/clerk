from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
import os
import re
from datetime import datetime

from ...db.base import get_db
from ...security.auth import get_current_user, ClerkUser
from ...services.roster_service import generate_roster
from ...core.config import settings

router = APIRouter(prefix="/rosters", tags=["rosters"])

SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _roster_dir() -> Path:
    # By convention, settings.roster_output_dir is relative to the API app directory
    # which matches where roster_service writes files (apps/api/files_roster_reports)
    return Path(settings.roster_output_dir)


@router.post("/generate")
async def generate_roster_endpoint(
        roster_type: str = Query(..., description="Either 'long' or 'short'"),
        db: Session = Depends(get_db),
        current_user: ClerkUser = Depends(get_current_user)
):
    roster_type_norm = (roster_type or "").strip().lower()
    if roster_type_norm not in {"long", "short"}:
        raise HTTPException(status_code=400, detail="Invalid roster_type. Must be 'long' or 'short'.")

    result = generate_roster(db, roster_type_norm)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate roster"))

    return result


@router.get("/list")
async def list_rosters(
        current_user: ClerkUser = Depends(get_current_user)
):
    directory = _roster_dir()
    files_info: List[dict] = []

    if not directory.exists():
        return {"files": []}

    try:
        for pdf in sorted(directory.glob("*.pdf")):
            try:
                stat = pdf.stat()
                files_info.append({
                    "name": pdf.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
                })
            except OSError:
                # Skip files we cannot stat
                continue
    except Exception:
        # On unexpected errors, return empty list rather than failing the whole request
        return {"files": []}

    return {"files": files_info}


@router.get("/download/{filename}")
async def download_roster(
        filename: str,
        current_user: ClerkUser = Depends(get_current_user)
):
    # Validate filename for safety
    if not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = _roster_dir() / filename

    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


@router.delete("/{filename}")
async def delete_roster(
        filename: str,
        db: Session = Depends(get_db),
        current_user: ClerkUser = Depends(get_current_user)
):
    # Validate filename
    if not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    directory = _roster_dir()
    pdf_path = directory / filename

    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="File not found")

    # Attempt deletion of PDF and corresponding TEX
    errors = []
    try:
        os.remove(pdf_path)
    except OSError as e:
        errors.append(str(e))

    base = pdf_path.with_suffix("")  # remove .pdf
    tex_path = base.with_suffix(".tex")
    if tex_path.exists():
        try:
            os.remove(tex_path)
        except OSError:
            # Non-fatal; continue
            pass

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {"success": True, "message": "Roster deleted successfully"}
