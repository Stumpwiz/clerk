"""Validation and transactional storage shared by generation and PDF imports."""
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import GeneratedLetter


def validate_filename(filename: str) -> None:
    if (not filename.endswith('.pdf') or '..' in filename
            or any(c in filename for c in '/\\')
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)):
        raise ValueError('Invalid PDF filename')


def save_generated_pdf(db: Session, filename: str, data: bytes) -> None:
    """Preserve the previous same-filename replacement behavior atomically.

    The caller commits. Keep the first creation timestamp when replacing bytes.
    """
    validate_filename(filename)
    statement = insert(GeneratedLetter).values(filename=filename, pdf_bytes=data)
    db.execute(statement.on_conflict_do_update(
        index_elements=[GeneratedLetter.filename], set_={'pdf_bytes': data},
    ))


def import_manifest(db: Session, manifest_path: Path, *, dry_run: bool = False) -> dict:
    """Verify all source bytes first; import all-or-nothing, refusing conflicts.

    Identical existing records are skipped. Dry runs never write database rows.
    """
    manifest_path = Path(manifest_path)
    files = json.loads(manifest_path.read_text())['files']
    verified = {}
    for item in files:
        name = item['filename']
        validate_filename(name)
        if name in verified:
            raise ValueError(f'Duplicate manifest filename: {name}')
        source = manifest_path.parent / name
        if source.is_symlink():
            raise ValueError(f'Symlink source refused: {name}')
        data = source.read_bytes()
        if (not data.startswith(b'%PDF-') or len(data) != item['size_bytes']
                or hashlib.sha256(data).hexdigest() != item['sha256']):
            raise ValueError(f'Integrity check failed: {name}')
        verified[name] = data

    inserted = skipped = 0
    try:
        for name, data in verified.items():
            if dry_run:
                existing = db.scalar(select(GeneratedLetter.pdf_bytes).where(
                    GeneratedLetter.filename == name))
                if existing is None:
                    inserted += 1
                    continue
            else:
                # ON CONFLICT waits for concurrent writers; never overwrite them.
                result = db.execute(insert(GeneratedLetter).values(
                    filename=name, pdf_bytes=data,
                ).on_conflict_do_nothing(index_elements=[GeneratedLetter.filename])
                    .returning(GeneratedLetter.filename)).scalar_one_or_none()
                if result is not None:
                    inserted += 1
                    continue
                existing = db.scalar(select(GeneratedLetter.pdf_bytes).where(
                    GeneratedLetter.filename == name).with_for_update())
            if existing != data:
                raise ValueError(f'Filename conflict (different content): {name}')
            skipped += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    return {'inserted' if not dry_run else 'would_insert': inserted, 'identical': skipped}
