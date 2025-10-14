import os
import re
import subprocess
from datetime import datetime
from typing import Dict, List
from pathlib import Path

from app.core.config import settings


def sanitize_latex(text: str) -> str:
    """
    Escape special LaTeX characters to prevent compilation errors.
    Based on prototype implementation.
    """
    if not text:
        return ""
    
    # Escape special LaTeX characters
    replacements = {
        '\\': r'\textbackslash{}',
        '%': r'\%',
        '$': r'\$',
        '&': r'\&',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}'
    }
    
    for char, escape in replacements.items():
        text = text.replace(char, escape)
    
    return text


def generate_pdf(
    header: str,
    body: str,
    addressee: str,
    salutation: str,
    date_str: str,
    apartment: str
) -> Dict[str, any]:
    """
    Generate a PDF letter from the template and parameters.
    
    Returns:
        dict: {
            "success": bool,
            "filename": str (if success),
            "error": str (if failure)
        }
    """
    # Create output directory if needed
    output_dir = Path(settings.pdf_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse date
    try:
        if date_str:
            effective_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            effective_date = datetime.today().date()
    except ValueError:
        effective_date = datetime.today().date()
    
    # Format date for LaTeX
    formatted_date = effective_date.strftime('%B %d, %Y').replace(' 0', ' ')
    date_iso = effective_date.strftime('%Y-%m-%d')
    
    # Extract last name for filename
    last_name = addressee.split()[-1] if addressee else 'Unknown'
    
    # Sanitize inputs
    recipient_safe = sanitize_latex(addressee)
    salutation_safe = sanitize_latex(salutation)
    apartment_safe = sanitize_latex(apartment)
    
    # Create LaTeX commands
    recipient_command = f"\\newcommand{{\\names}}{{{recipient_safe}}}"
    salutation_command = f"\\newcommand{{\\salutation}}{{{salutation_safe}}}"
    apartment_command = f"\\newcommand{{\\apartment}}{{{apartment_safe}}}"
    date_command = f"\\date{{{formatted_date}}}"
    
    # Sanitize template
    header_safe = re.sub(r"(\r\n|\r|\n)+", "\n", header.strip())
    body_safe = re.sub(r"(\r\n|\r|\n)+", "\n", body.strip())
    
    # Combine into full document
    tex_content = (
        f"{header_safe}\n"
        f"{recipient_command}\n"
        f"{salutation_command}\n"
        f"{apartment_command}\n"
        f"{date_command}\n"
        f"{body_safe}"
    )
    
    # Build filename
    safe_base = f"{date_iso}_{last_name}"
    tex_file = output_dir / f"{safe_base}.tex"
    pdf_file = output_dir / f"{safe_base}.pdf"
    
    try:
        # Write .tex file
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)
        
        # Run xelatex with detailed logging
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting xelatex for {safe_base}.tex")
        logger.info(f"Working directory: {output_dir}")
        logger.info(f"xelatex path: {settings.xelatex_path}")
        logger.info(f"Output directory: {output_dir}")
        
        result = subprocess.run(
            [
                settings.xelatex_path,
                "-interaction=nonstopmode",
                f"{safe_base}.tex"
            ],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Log results
        logger.info(f"xelatex return code: {result.returncode}")
        logger.info(f"stdout length: {len(result.stdout)} chars")
        logger.info(f"stderr length: {len(result.stderr)} chars")
        
        if result.returncode != 0:
            logger.error(f"xelatex failed with code {result.returncode}")
            logger.error(f"stderr: {result.stderr}")
            logger.error(f"stdout preview: {result.stdout[:1000]}")
        
        # Give filesystem time to sync (Windows issue)
        import time
        time.sleep(0.2)
        
        # Check if PDF was created
        logger.info(f"Checking for PDF at: {pdf_file}")
        logger.info(f"PDF exists: {pdf_file.exists()}")
        
        # List all files in directory for debugging
        all_files = list(output_dir.glob("*"))
        logger.info(f"Files in output directory: {[f.name for f in all_files]}")
        
        if pdf_file.exists():
            # Clean up auxiliary files
            aux_extensions = ['.aux', '.log', '.out', '.toc', '.lof', '.lot', 
                            '.fls', '.fdb_latexmk', '.synctex.gz', '.dvi']
            
            for file in output_dir.glob(f"{safe_base}.*"):
                if file.suffix in aux_extensions:
                    try:
                        file.unlink()
                    except Exception:
                        pass
            
            return {
                "success": True,
                "filename": f"{safe_base}.pdf"
            }
        else:
            # Extract error from log
            error_msg = "PDF generation failed. Check LaTeX template syntax."
            if result.returncode != 0 and "! " in result.stdout:
                errors = [line.strip() for line in result.stdout.split('\n') if "! " in line]
                if errors:
                    error_msg = f"LaTeX error: {errors[0]}"
            
            return {
                "success": False,
                "error": error_msg
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "PDF generation timed out (>30 seconds)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def list_pdfs() -> List[Dict[str, any]]:
    """
    List all PDF files in the output directory.
    
    Returns:
        list: [{"filename": str, "created": str, "size": int}, ...]
        Sorted alphabetically by filename.
    """
    output_dir = Path(settings.pdf_output_dir)
    
    if not output_dir.exists():
        return []
    
    pdfs = []
    for pdf_file in output_dir.glob("*.pdf"):
        stat = pdf_file.stat()
        pdfs.append({
            "filename": pdf_file.name,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "size": stat.st_size
        })
    
    # Sort alphabetically
    pdfs.sort(key=lambda x: x["filename"])
    
    return pdfs


def delete_pdf(filename: str) -> bool:
    """
    Delete a PDF file.
    
    Returns:
        bool: True if deleted, False if not found
    """
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    
    output_dir = Path(settings.pdf_output_dir)
    pdf_file = output_dir / filename
    
    if pdf_file.exists() and pdf_file.suffix == ".pdf":
        try:
            pdf_file.unlink()
            return True
        except Exception:
            return False
    
    return False
