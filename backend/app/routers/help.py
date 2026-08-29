"""Authenticated access to Clerk help documents."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.auth.dependencies import require_authenticated_user


router = APIRouter(
    prefix="/api/help",
    tags=["help"],
    dependencies=[Depends(require_authenticated_user)],
)

GUIDE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "static"
    / "documents"
    / "administrative-assistant-user-guide.pdf"
)
GUIDE_FILENAME = "Administrative Assistant User Guide.pdf"


@router.get("/administrative-assistant-user-guide")
def get_administrative_assistant_user_guide() -> FileResponse:
    """Open the printable Administrative Assistant guide."""
    return FileResponse(
        path=str(GUIDE_PATH),
        media_type="application/pdf",
        filename=GUIDE_FILENAME,
        headers={"Content-Disposition": f'inline; filename="{GUIDE_FILENAME}"'},
    )
