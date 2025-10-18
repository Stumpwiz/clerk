"""
Jinja2 template utilities for LaTeX document generation.

See docs/TEMPLATE_SYSTEM.md for complete documentation on the template system,
available variables, and usage examples.

Utility functions for loading and rendering LaTeX-oriented Jinja2 templates.

This module centralizes Jinja2 environment configuration and file-system
resolution for templates used in roster/report generation. It intentionally
uses custom Jinja2 delimiters that are less likely to conflict with LaTeX
syntax.

Custom Jinja2 delimiters used here (prototype-compatible):
- Blocks: \\BLOCK{ ... }
- Variables: \\VAR{ ... }
- Comments: \\%{ ... }

Why custom delimiters?
- Standard Jinja2 delimiters (e.g., {% %} and {{ }}) can collide with LaTeX
  braces and commands, producing confusing errors. The prototype chose
  alternative delimiters that blend better with LaTeX sources.

Path resolution:
- The templates directory is defined by settings.templates_dir and is treated
  as relative to the API app root (apps/api/) by default. This mirrors the
  file-system handling used for roster outputs in roster_service._get_output_dir.

Notes on escaping:
- autoescape is disabled because we are generating LaTeX, not HTML. Ensure
  any user-provided content is LaTeX-sanitized before rendering.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from jinja2.exceptions import TemplateError

from ..core.config import settings

# Module-level logger
logger = logging.getLogger(__name__)


def get_template_dir() -> Path:
    """Resolve and ensure the templates directory exists.

    Resolution strategy:
    - Determine the path to this module (apps/api/app/services/...).
    - Navigate up to the API app root directory (apps/api/).
    - Append the configured templates directory (settings.templates_dir),
      which by convention is relative to apps/api/ (e.g., "app/templates").
    - Create the directory if it does not exist.

    Custom Jinja2 delimiters context:
    - Templates located here are expected to use custom delimiters:
      blocks <% %>, variables << >>, and comments <# #>. This avoids LaTeX
      syntax conflicts.

    Returns:
    - Absolute Path to the templates directory.

    Raises:
    - OSError: If the directory cannot be created due to permission issues or
      invalid paths.
    """
    # Get the directory where this module resides (apps/api/app/services/)
    current_file = Path(__file__).resolve()
    # Navigate up to apps/api/
    api_root = current_file.parent.parent.parent
    # Build path to the templates directory using settings.templates_dir
    template_dir = api_root / settings.templates_dir
    # Create the directory if it doesn't exist
    template_dir.mkdir(parents=True, exist_ok=True)

    logger.debug("Resolved template directory: %s", template_dir)
    return template_dir


def _create_jinja_env() -> Environment:
    """Create Jinja2 environment with custom delimiters for LaTeX compatibility.

    The environment uses a FileSystemLoader rooted at the directory returned by
    get_template_dir() and custom delimiters matching our LaTeX templates:
      - block_start_string: '\\BLOCK{'
      - block_end_string: '}'
      - variable_start_string: '\\VAR{'
      - variable_end_string: '}'
      - comment_start_string: '\\%{'
      - comment_end_string: '}'

    autoescape is disabled because rendered content targets LaTeX. Make sure to
    pre-sanitize any user-supplied text for LaTeX special characters.

    Returns:
    - A configured Jinja2 Environment instance.
    """
    template_dir = get_template_dir()
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        block_start_string='\\BLOCK{',
        block_end_string='}',
        variable_start_string='\\VAR{',
        variable_end_string='}',
        comment_start_string='\\%{',
        comment_end_string='}',
        autoescape=False,  # We're generating LaTeX, not HTML
    )
    logger.debug("Created Jinja2 Environment with template dir: %s", template_dir)
    return env


def load_and_render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Load a LaTeX Jinja2 template by name and render it with a context.

    Parameters:
    - template_name: Name of the template file to load from the templates
      directory (e.g., "long_form_roster_template.tex").
    - context: Mapping of variables referenced by the template. Typical keys
      include general metadata like "generated" and "title", and data
      structures like "grouped" that contain the records formatted for
      rendering. The exact shape is determined by the specific template, but
      should map to primitives (str, int), sequences, or simple objects with
      attribute access.

    Custom Jinja2 delimiters:
    - Blocks <% %>
    - Variables << >>
    - Comments <# #>

    Returns:
    - The rendered LaTeX source as a string.

    Raises:
    - FileNotFoundError: If the named template cannot be located.
    - ValueError: If rendering fails due to template logic errors or context
      mismatches. The original exception message is included for diagnostics.
    - OSError: If underlying file system errors occur while resolving the
      template directory.
    """
    log = logger
    try:
        env = _create_jinja_env()
    except OSError as e:
        log.error("Failed to initialize Jinja environment: %s", e)
        raise

    log.info("Loading template: %s", template_name)
    try:
        template = env.get_template(template_name)
    except TemplateNotFound as e:
        log.error("Template not found: %s (search path: %s)", template_name, get_template_dir())
        raise FileNotFoundError(f"Template '{template_name}' not found in '{get_template_dir()}'") from e
    except Exception as e:  # Catch unexpected loader errors
        log.error("Unexpected error loading template '%s': %s", template_name, e)
        raise

    log.debug("Rendering template '%s' with context keys: %s", template_name, list(context.keys()))
    try:
        rendered = template.render(**context)
    except TemplateError as e:
        log.error("Jinja2 template rendering failed for '%s': %s", template_name, e)
        raise ValueError(f"Failed to render template '{template_name}': {e}") from e
    except Exception as e:
        log.error("Unexpected error during rendering for '%s': %s", template_name, e)
        raise ValueError(f"Unexpected error rendering template '{template_name}': {e}") from e

    log.info("Successfully rendered template: %s", template_name)
    return rendered
