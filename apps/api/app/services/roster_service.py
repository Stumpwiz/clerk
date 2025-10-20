from __future__ import annotations

"""Roster PDF generation using Jinja2 LaTeX templates.

Uses templates from app/templates/ to generate formatted rosters.
See docs/TEMPLATE_SYSTEM.md for template documentation.
"""

import logging
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_, select, func

from ..db.models import Term, Person, Body, Office
from ..core.config import settings
from .template_utils import load_and_render_template


def sanitize_latex(text: str) -> str:
    """
    Escape special LaTeX characters: &, %, $, #, _, {, }, ~, ^, \
    Handle None by returning an empty string.
    Mirrors behavior used in pdf_service.py for consistency.
    """
    if not text:
        return ""

    replacements = {
        "\\": r"\textbackslash{}",
        "%": r"\%",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }

    for ch, esc in replacements.items():
        text = text.replace(ch, esc)
    return text


def _get_output_dir() -> Path:
    """Get the roster output directory as an absolute path."""
    # Get the directory where this module resides (apps/api/app/services/)
    current_file = Path(__file__).resolve()
    # Navigate up to apps/api/
    api_root = current_file.parent.parent.parent
    # Build path to files_roster_reports
    output_dir = api_root / settings.roster_output_dir
    # Create if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _group_terms(rows: List[Tuple[Body, Office, Person]]) -> Dict[int, Dict[int, List[Person]]]:
    """
    Group by Body then Office.
    Returns mapping: body_id -> { office_id -> [Person, ...] }
    """
    grouped: Dict[int, Dict[int, List[Person]]] = {}
    for b, o, p in rows:
        bod = grouped.setdefault(b.body_id, {})
        bod.setdefault(o.office_id, []).append(p)
    return grouped


def generate_roster(db: Session, roster_type: str) -> Dict[str, Any]:
    """
    Generate a roster PDF (long or short) using Jinja2 LaTeX templates.

    This preserves the existing data querying and grouping logic, but replaces the
    hardcoded LaTeX string assembly with template-based rendering. The selected
    template is rendered with a structured context and then compiled with xelatex.

    Args:
        db: SQLAlchemy Session
        roster_type: "long" or "short"

    Returns:
        A dict including {"success": True, "filename": <pdf_name>, "type": <roster_type>} on success,
        or {"success": False, "error": <message>} on failure.
    """
    logger = logging.getLogger(__name__)

    roster_type = (roster_type or "").strip().lower()
    if roster_type not in {"long", "short"}:
        return {"success": False, "error": "Invalid roster_type. Expected 'long' or 'short'."}

    today = date.today()

    try:
        # Build query: active terms (end is NULL or >= today)
        stmt = (
            select(Body, Office, Person)
            .join(Office, Office.office_body_id == Body.body_id)
            .join(Term, Term.termofficeid == Office.office_id)
            .join(Person, Person.personid == Term.termpersonid)
            .where(or_(Term.end.is_(None), Term.end >= today))
            .order_by(
                Body.body_precedence.asc(),
                func.coalesce(Office.office_precedence, 999999).asc(),
                func.lower(func.coalesce(Person.first, '')).asc(),
                func.lower(func.coalesce(Person.last, '')).asc(),
            )
        )
        result = db.execute(stmt)
        rows: List[Tuple[Body, Office, Person]] = [(b, o, p) for b, o, p in result.all()]

        # For section titles we also need fast lookup of Body/Office objects in order
        # Build ordered unique lists
        bodies: List[Body] = []
        offices_by_body: Dict[int, List[Office]] = {}
        seen_bodies = set()
        seen_offices: set[Tuple[int, int]] = set()
        for b, o, _ in rows:
            if b.body_id not in seen_bodies:
                bodies.append(b)
                seen_bodies.add(b.body_id)
            key = (b.body_id, o.office_id)
            if key not in seen_offices:
                offices_by_body.setdefault(b.body_id, []).append(o)
                seen_offices.add(key)

        grouped_people = _group_terms(rows)

    except Exception as e:
        logger.exception("Failed to query roster data")
        return {"success": False, "error": f"Database query error: {e}"}

    # Build LaTeX content using Jinja2 templates
    try:
        # Build template context
        context: Dict[str, Any] = {
            "generated": today.strftime('%B %d, %Y'),
            "title": 'Long Form Roster' if roster_type == 'long' else 'Short Form Roster',
            "grouped": []
        }

        # Build hierarchical grouped data for template
        for body in bodies:
            body_data: Dict[str, Any] = {
                'body_name': sanitize_latex(body.name or ''),
                'offices': []
            }
            for office in offices_by_body.get(body.body_id, []):
                office_data: Dict[str, Any] = {
                    'office_title': sanitize_latex(office.title or ''),
                    'people': []
                }
                people = grouped_people.get(body.body_id, {}).get(office.office_id, [])
                for person in people:
                    person_data: Dict[str, Any] = {
                        'name': f"{sanitize_latex(person.first or '')} {sanitize_latex(person.last or '')}",
                    }
                    if roster_type == 'long':
                        person_data['apt'] = sanitize_latex(person.apt or '')
                        person_data['phone'] = sanitize_latex(person.phone or '')
                        person_data['email'] = sanitize_latex(person.email or '')
                    else:
                        person_data['office_title'] = sanitize_latex(office.title or '')
                    office_data['people'].append(person_data)
                body_data['offices'].append(office_data)
            context['grouped'].append(body_data)

        # Choose template based on type
        template_name = (
            'long_form_roster_template.tex' if roster_type == 'long' else 'short_form_roster_template.tex'
        )
        logger.info(f"Rendering template: {template_name}")
        try:
            tex_content = load_and_render_template(template_name, context)
        except (FileNotFoundError, ValueError) as te:
            logger.error("Template rendering failed: %s", te)
            return {"success": False, "error": f"Template error: {te}"}

        # Write files
        output_dir = _get_output_dir()
        date_iso = today.strftime("%Y-%m-%d")
        base = f"{date_iso}_roster_{roster_type}"
        tex_path = output_dir / f"{base}.tex"
        pdf_path = output_dir / f"{base}.pdf"

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        # Compile with xelatex
        logger.info(f"Starting xelatex for {tex_path.name}")
        logger.info(f"Working directory: {output_dir}")
        logger.info(f"xelatex path: {settings.xelatex_path}")

        result = subprocess.run(
            [settings.xelatex_path, "-interaction=nonstopmode", tex_path.name],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )

        logger.info(f"xelatex return code: {result.returncode}")
        logger.info(f"stdout length: {len(result.stdout)} chars")
        logger.info(f"stderr length: {len(result.stderr)} chars")
        if result.returncode != 0:
            logger.error("xelatex failed")
            logger.error(result.stderr[:2000])

        # Allow FS to settle on Windows
        try:
            import time
            time.sleep(0.2)
        except Exception:
            pass

        if pdf_path.exists():
            # cleanup aux files
            aux_exts = [
                ".aux",
                ".log",
                ".out",
                ".toc",
                ".fls",
                ".fdb_latexmk",
                ".synctex.gz",
            ]
            for f in output_dir.glob(f"{base}.*"):
                if f.suffix in aux_exts or f.name.endswith(".synctex.gz"):
                    try:
                        f.unlink()
                    except Exception:
                        pass

            return {"success": True, "filename": f"{base}.pdf", "type": roster_type}

        # Not found -> failure
        # Attempt to extract a LaTeX error message
        error_msg = "PDF generation failed. Check LaTeX content."
        if result.returncode != 0 and "! " in result.stdout:
            for line in result.stdout.splitlines():
                if line.strip().startswith("! "):
                    error_msg = f"LaTeX error: {line.strip()}"
                    break
        return {"success": False, "error": error_msg}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "PDF generation timed out (>30 seconds)"}
    except OSError as e:
        return {"success": False, "error": f"File error: {e}"}
    except Exception as e:
        logger.exception("Unexpected error generating roster")
        return {"success": False, "error": f"Unexpected error: {e}"}
