# app/utils/pdf_generator.py - PDF generation utilities for rosters and reports

import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader


class PDFGenerator:
    """Handles LaTeX-based PDF generation for rosters and reports"""

    def __init__(self, reports_dir: str = "files_roster_reports"):
        """
        Initialize PDF generator

        Args:
            reports_dir: Directory containing templates and generated files
        """
        # Get absolute path to reports directory
        backend_dir = Path(__file__).parent.parent.parent
        self.reports_dir = backend_dir / reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Configure Jinja2 environment for LaTeX
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.reports_dir)),
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

        # Render template
        template = self.jinja_env.get_template(template_name)
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

        # Clean up auxiliary files including the .tex source
        for ext in [".aux", ".log", ".tex"]:
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
