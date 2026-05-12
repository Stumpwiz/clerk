from dataclasses import dataclass
from typing import Callable, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.utils.mailing_lists import (
    get_committee_chairs_emails,
    get_committee_secretaries_emails,
    get_hall_reps_emails,
    get_rc_officers_emails,
    write_email_list_file,
)
from app.utils.pdf_generator import PDFGenerator

router = APIRouter(prefix="/api/mailing-lists", tags=["mailing-lists"])

pdf_generator = PDFGenerator(settings.roster_reports_dir)


@dataclass
class MailingListRegistryEntry:
    id: str
    label: str
    description: str
    filename: str
    builder_func: Callable[[Session], List[str]]


class MailingListMetadata(BaseModel):
    id: str
    label: str
    description: str
    filename: str
    renderer_type: str


MAILING_LIST_REGISTRY: Dict[str, MailingListRegistryEntry] = {
    "committee-chairs": MailingListRegistryEntry(
        id="committee-chairs",
        label="Committee Chairs",
        description='Email list for members with a current Office title exactly "Chair"',
        filename="committee_chairs.txt",
        builder_func=get_committee_chairs_emails,
    ),
    "committee-secretaries": MailingListRegistryEntry(
        id="committee-secretaries",
        label="Committee Secretaries",
        description='Email list for members with a current Office title exactly "Secretary"',
        filename="committee_secretaries.txt",
        builder_func=get_committee_secretaries_emails,
    ),
    "hall-reps": MailingListRegistryEntry(
        id="hall-reps",
        label="Hall Reps",
        description="Email list for active hall reps",
        filename="hall_reps.txt",
        builder_func=get_hall_reps_emails,
    ),
    "rc-officers": MailingListRegistryEntry(
        id="rc-officers",
        label="Residents Council Officers",
        description="Email list for Residents Council officers",
        filename="rc_officers.txt",
        builder_func=get_rc_officers_emails,
    ),
}


@router.get("", response_model=List[MailingListMetadata])
async def list_mailing_lists():
    return [
        MailingListMetadata(
            id=entry.id,
            label=entry.label,
            description=entry.description,
            filename=entry.filename,
            renderer_type="plain_text_file",
        )
        for entry in MAILING_LIST_REGISTRY.values()
    ]


@router.get("/{list_id}")
async def generate_mailing_list(list_id: str, db: Session = Depends(get_db)):
    entry = MAILING_LIST_REGISTRY.get(list_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Mailing list not found")

    try:
        emails = entry.builder_func(db)
        output_path = write_email_list_file(pdf_generator.reports_dir, entry.filename, emails)
        return FileResponse(
            path=str(output_path),
            media_type="text/plain; charset=utf-8",
            filename=entry.filename,
            headers={"Content-Disposition": f"inline; filename={entry.filename}"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
