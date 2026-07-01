from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.config import settings
from app.routers import reports
from app.utils.ionos_publisher import IONOSPublisherError


def test_short_roster_publish_skips_before_upload_when_disabled(monkeypatch, caplog):
    monkeypatch.setattr(settings, "enable_ionos_roster_publish", False)

    def fail_if_called(**_kwargs):
        raise AssertionError("upload_pdf_to_ionos should not be called when publishing is disabled")

    monkeypatch.setattr(reports, "upload_pdf_to_ionos", fail_if_called)

    with caplog.at_level(logging.INFO, logger=reports.logger.name):
        reports._publish_short_roster_to_ionos(Path("does-not-need-to-exist.pdf"))

    assert "IONOS roster publication skipped (disabled for local development)." in caplog.text


def test_short_roster_publish_failure_is_logged_not_raised(monkeypatch, tmp_path, caplog):
    pdf_path = tmp_path / "short_form_roster.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(settings, "enable_ionos_roster_publish", True)

    def raise_publish_error(**_kwargs):
        raise IONOSPublisherError("Unable to fetch IONOS SFTP secret from AWS Secrets Manager.")

    monkeypatch.setattr(reports, "upload_pdf_to_ionos", raise_publish_error)

    with caplog.at_level(logging.ERROR, logger=reports.logger.name):
        reports._publish_short_roster_to_ionos(pdf_path)

    assert "IONOS short roster publish failed" in caplog.text


def test_non_short_roster_has_no_publication_side_effect(monkeypatch, tmp_path):
    report = reports.ReportRegistryEntry(
        id="long-roster",
        label="Long Form Roster",
        description="Full roster",
        filename="long_form_roster.pdf",
        renderer_type="latex_pdf",
    )

    def fail_if_called(_pdf_path):
        raise AssertionError("short roster publication should not run for other reports")

    monkeypatch.setattr(reports, "_publish_short_roster_to_ionos", fail_if_called)

    reports._run_post_generation_side_effects(report, tmp_path / "long_form_roster.pdf")
