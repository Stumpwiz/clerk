from __future__ import annotations

"""
Report PDF generation using Jinja2 LaTeX templates.

Uses templates from app/templates/ to generate formatted reports.
See docs/TEMPLATE_SYSTEM.md for template documentation.

Services for generating PDF reports (expirations and vacancies) using Jinja2 LaTeX templates.

This module follows the same structure and conventions as roster_service.py:
- Path resolution treats output directories as relative to the API app root (apps/api/).
- Templates are rendered via the shared template_utils with custom Jinja2 delimiters.
- xelatex is invoked to compile rendered .tex files to PDF.
- Robust error handling and logging are provided for DB, template, file, and compilation steps.
"""

import logging
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import text

from .template_utils import load_and_render_template
from ..core.config import settings

logger = logging.getLogger(__name__)


def sanitize_latex(text_value: str) -> str:
    """
    Escape special LaTeX characters in a string.

    This function mirrors sanitize_latex() from roster_service.py to ensure
    consistent escaping across all LaTeX-generating services.

    Escapes: &, %, $, #, _, {, }, ~, ^, \

    Args:
        text_value: Input string which may contain LaTeX special characters. If None or empty,
                    an empty string is returned.

    Returns:
        A string safe for LaTeX rendering with special characters escaped.
    """
    if not text_value:
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

    text_escaped = text_value
    for ch, esc in replacements.items():
        text_escaped = text_escaped.replace(ch, esc)
    return text_escaped


def _get_reports_output_dir() -> Path:
    """Get the reports output directory as an absolute path.

    Follows the same pattern as roster_service._get_output_dir():
    - Determine the path to this module (apps/api/app/services/)
    - Navigate up to the API app root (apps/api/)
    - Append settings.roster_output_dir (reports share the same location as rosters)
    - Ensure the directory exists

    Returns:
        Absolute Path to the output directory used for both rosters and reports.
    """
    current_file = Path(__file__).resolve()
    api_root = current_file.parent.parent.parent  # apps/api/
    output_dir = api_root / settings.roster_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _fetch_expiring_terms_current_year(db: Session) -> tuple[List[Dict[str, Any]], int]:
    """Fetch terms expiring within the current calendar year.

    Excludes never-expiring sentinel date 9999-12-31 and NULLs.
    Returns a tuple of (rows, year).
    """
    today = date.today()
    year = today.year
    begin = f"{year}-01-01"
    end = f"{year}-12-31"

    query = text(
        """
        SELECT 
            person.first,
            person.last,
            person.email,
            body.name as body_name,
            office.title as office_title,
            term.end as term_end_date
        FROM term
        JOIN person ON person.personid = term.termpersonid
        JOIN office ON office.office_id = term.termofficeid
        JOIN body ON body.body_id = office.office_body_id
        WHERE term.end IS NOT NULL
          AND term.end != date('9999-12-31')
          AND term.end BETWEEN :begin AND :end
        ORDER BY body.body_precedence ASC,
                 COALESCE(office.office_precedence, 999999) ASC,
                 lower(COALESCE(person.first, '')) ASC,
                 lower(COALESCE(person.last, '')) ASC,
                 term.end
        """
    )
    result = db.execute(query, {"begin": begin, "end": end})
    rows: List[Dict[str, Any]] = [dict(row._mapping) for row in result]
    return rows, year


def generate_expirations_report(db: Session) -> Dict[str, Any]:
    """
    Generate a PDF report of terms expiring in the current calendar year.
    """
    today = date.today()
    try:
        rows, report_year = _fetch_expiring_terms_current_year(db)
    except Exception as e:
        logger.exception("Failed to query expirations report data")
        return {"success": False, "error": f"Database query error: {e}"}

    # Build template context
    try:
        context: Dict[str, Any] = {
            'generated': today.strftime('%B %d, %Y'),
            'report_year': report_year,
            'expirations': []
        }

        for row in rows:
            context['expirations'].append({
                'name': f"{sanitize_latex(row.get('first') or '')} {sanitize_latex(row.get('last') or '')}",
                'email': sanitize_latex(row.get('email') or ''),
                'body_name': sanitize_latex(row.get('body_name') or ''),
                'office_title': sanitize_latex(row.get('office_title') or ''),
                'term_end_date': row.get('term_end_date'),
            })

        template_name = 'expirations_report_template.tex'
        logger.info("Rendering template: %s", template_name)
        try:
            tex_content = load_and_render_template(template_name, context)
        except (FileNotFoundError, ValueError) as te:
            logger.error("Template rendering failed: %s", te)
            return {"success": False, "error": f"Template error: {te}"}

        # Write TEX and compile to PDF
        output_dir = _get_reports_output_dir()
        date_iso = today.strftime("%Y-%m-%d")
        base = f"{date_iso}_report_expirations"
        tex_path = output_dir / f"{base}.tex"
        pdf_path = output_dir / f"{base}.pdf"

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        logger.info("Starting xelatex for %s", tex_path.name)
        logger.info("Working directory: %s", output_dir)
        logger.info("xelatex path: %s", settings.xelatex_path)

        result = subprocess.run(
            [settings.xelatex_path, "-interaction=nonstopmode", tex_path.name],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )

        logger.info("xelatex return code: %s", result.returncode)
        logger.info("stdout length: %s chars", len(result.stdout))
        logger.info("stderr length: %s chars", len(result.stderr))
        if result.returncode != 0:
            logger.error("xelatex failed")
            logger.error(result.stderr[:2000])

        # Allow FS settle (Windows)
        try:
            import time
            time.sleep(0.2)
        except Exception:
            pass

        if pdf_path.exists():
            # Cleanup aux files
            aux_exts = [
                ".aux",
                ".log",
                ".out",
                ".toc",
                ".fls",
                ".fdb_latexmk",
                ".synctex.gz",
            ]
            for fpath in output_dir.glob(f"{base}.*"):
                if fpath.suffix in aux_exts or fpath.name.endswith(".synctex.gz"):
                    try:
                        fpath.unlink()
                    except Exception:
                        pass

            return {"success": True, "filename": f"{base}.pdf", "type": "expirations"}

        # If compilation didn't produce a PDF, attempt to extract a LaTeX error
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
        logger.exception("Unexpected error generating expirations report")
        return {"success": False, "error": f"Unexpected error: {e}"}


def generate_vacancies_report(db: Session) -> Dict[str, Any]:
    """
    Generate a PDF report listing current vacant offices.

    Uses a raw SQL query to identify offices with no active term incumbent, renders
    a LaTeX template (vacancies_report_template.tex) via Jinja2, writes the TEX
    source, compiles with xelatex, and returns the resulting PDF filename.

    Args:
        db: SQLAlchemy Session for database access.

    Returns:
        Dict with success status and filename on success:
          {"success": True, "filename": "<pdf_name>", "type": "vacancies"}
        or an error payload on failure:
          {"success": False, "error": "<message>"}
    """
    today = date.today()
    try:
        query = text(
            """
            SELECT 
                body.name as body_name,
                office.title as office_title,
                office.office_precedence,
                person.first as incumbent_first
            FROM term
            JOIN office ON office.office_id = term.termofficeid
            JOIN body ON body.body_id = office.office_body_id
            JOIN person ON person.personid = term.termpersonid
            WHERE (term.end IS NULL OR term.end > date('now'))
              AND lower(COALESCE(person.first, '')) = lower('(Vacant)')
            ORDER BY body.body_precedence ASC,
                     COALESCE(office.office_precedence, 999999) ASC
            """
        )
        result = db.execute(query)
        rows: List[Dict[str, Any]] = [dict(row._mapping) for row in result]
    except Exception as e:
        logger.exception("Failed to query vacancies report data")
        return {"success": False, "error": f"Database query error: {e}"}

    try:
        # Build template context (include title and grouped data preserving SQL order)
        generated_str = today.strftime('%B %d, %Y')

        # Build both a flat list and a grouped structure to avoid Jinja groupby re-sorting
        vacancies_list: List[Dict[str, Any]] = []
        grouped: List[Dict[str, Any]] = []
        current_body: str | None = None

        for row in rows:
            body_name = sanitize_latex(row.get('body_name') or '')
            office_title = sanitize_latex(row.get('office_title') or '')
            incumbent_name = sanitize_latex(row.get('incumbent_first') or '(Vacant)')

            vacancies_list.append({
                'body_name': body_name,
                'office_title': office_title,
                'incumbent': incumbent_name,
            })

            if current_body != body_name:
                grouped.append({'body_name': body_name, 'entries': []})
                current_body = body_name
            grouped[-1]['entries'].append({'office_title': office_title, 'incumbent': incumbent_name})

        context: Dict[str, Any] = {
            'generated': generated_str,
            'title': 'Vacancies',
            'vacancies': vacancies_list,
            'grouped': grouped,
        }

        template_name = 'vacancies_report_template.tex'
        logger.info("Rendering template: %s", template_name)
        try:
            tex_content = load_and_render_template(template_name, context)
        except (FileNotFoundError, ValueError) as te:
            logger.error("Template rendering failed: %s", te)
            return {"success": False, "error": f"Template error: {te}"}

        # Write TEX and compile
        output_dir = _get_reports_output_dir()
        date_iso = today.strftime("%Y-%m-%d")
        base = f"{date_iso}_report_vacancies"
        tex_path = output_dir / f"{base}.tex"
        pdf_path = output_dir / f"{base}.pdf"

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        logger.info("Starting xelatex for %s", tex_path.name)
        logger.info("Working directory: %s", output_dir)
        logger.info("xelatex path: %s", settings.xelatex_path)

        result = subprocess.run(
            [settings.xelatex_path, "-interaction=nonstopmode", tex_path.name],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )

        logger.info("xelatex return code: %s", result.returncode)
        logger.info("stdout length: %s chars", len(result.stdout))
        logger.info("stderr length: %s chars", len(result.stderr))
        if result.returncode != 0:
            logger.error("xelatex failed")
            logger.error(result.stderr[:2000])

        # Allow FS settle (Windows)
        try:
            import time
            time.sleep(0.2)
        except Exception:
            pass

        if pdf_path.exists():
            # Cleanup aux files
            aux_exts = [
                ".aux",
                ".log",
                ".out",
                ".toc",
                ".fls",
                ".fdb_latexmk",
                ".synctex.gz",
            ]
            for fpath in output_dir.glob(f"{base}.*"):
                if fpath.suffix in aux_exts or fpath.name.endswith(".synctex.gz"):
                    try:
                        fpath.unlink()
                    except Exception:
                        pass

            return {"success": True, "filename": f"{base}.pdf", "type": "vacancies"}

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
        logger.exception("Unexpected error generating vacancies report")
        return {"success": False, "error": f"Unexpected error: {e}"}
