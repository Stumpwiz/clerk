# app/utils/pdf_generator.py - PDF generation utilities for rosters and reports

import subprocess
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any
from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_DIR = BACKEND_ROOT / "files_roster_reports"


class PDFGenerator:
    """Handles LaTeX-based PDF generation for rosters and reports"""

    def __init__(self, reports_dir: str = "files_roster_reports"):
        """
        Initialize PDF generator

        Args:
            reports_dir: Directory containing templates and generated files
        """
        # Get absolute path to reports directory
        self.reports_dir = BACKEND_ROOT / reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Configure Jinja2 environment for LaTeX
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(DEFAULT_TEMPLATE_DIR)),
            block_start_string='\\BLOCK{',
            block_end_string='}',
            variable_start_string='\\VAR{',
            variable_end_string='}',
            comment_start_string='\\%{',
            comment_end_string='}',
            autoescape=False
        )

    def generate_pdf(
            self,
            template_name: str,
            output_name: str,
            context: Dict[str, Any]
    ) -> Path:
        """
        Generate a PDF from a LaTeX template

        Args:
            template_name: Name of the .tex template file
            output_name: Base name for output files (without extension)
            context: Template context dictionary

        Returns:
            Path to generated PDF file

        Raises:
            RuntimeError: If PDF generation fails
        """
        tex_filename = f"{output_name}.tex"
        pdf_filename = f"{output_name}.pdf"
        tex_path = self.reports_dir / tex_filename
        pdf_path = self.reports_dir / pdf_filename

        template_path = DEFAULT_TEMPLATE_DIR / template_name
        if not template_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Report template not found at {template_path}"
            )

        template_source = template_path.read_text(encoding="utf-8")
        template = self.jinja_env.from_string(template_source)
        rendered_tex = template.render(**context)

        # Write .tex file
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(rendered_tex)

        # Clean up old auxiliary files
        for ext in [".aux", ".log", ".synctex.gz"]:
            aux_file = self.reports_dir / f"{output_name}{ext}"
            if aux_file.exists():
                aux_file.unlink()

        # Compile with xelatex
        logo_source = BACKEND_ROOT / "static" / "images" / "residentCouncilLogoSmall.jpg"
        logo_target = self.reports_dir / "residentCouncilLogoSmall.jpg"
        if not logo_source.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Report logo not found at {logo_source}"
            )
        shutil.copyfile(logo_source, logo_target)

        result = subprocess.run(
            [
                "xelatex",
                "-interaction=nonstopmode",
                "-output-directory",
                str(self.reports_dir),
                str(tex_path)
            ],
            cwd=str(self.reports_dir),
            capture_output=True,
            text=True
        )

        # Check if PDF was created
        if not pdf_path.exists():
            error_msg = (
                f"PDF generation failed for {output_name}\n\n"
                f"LaTeX stdout:\n{result.stdout}\n\n"
                f"LaTeX stderr:\n{result.stderr}"
            )
            raise RuntimeError(error_msg)

        # Clean up auxiliary files
        for ext in [".aux", ".tex", ".log", ".synctex.gz"]:
            aux_file = self.reports_dir / f"{output_name}{ext}"
            if aux_file.exists():
                aux_file.unlink()

        return pdf_path

    @staticmethod
    def get_generation_timestamp() -> str:
        """Get formatted timestamp for report generation in Eastern Time (ET)"""
        # Use America/New_York timezone which automatically handles EST/EDT
        eastern = ZoneInfo("America/New_York")
        now_eastern = datetime.now(eastern)
        # Format with timezone abbreviation (EST or EDT)
        return now_eastern.strftime("%Y-%m-%d %H:%M:%S %Z")
