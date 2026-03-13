"""Utilities for publishing generated roster PDFs to IONOS over SFTP."""

import json
import logging
import posixpath
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
try:
    import paramiko
except ImportError:  # pragma: no cover - optional dependency in local/dev environments
    paramiko = None

logger = logging.getLogger(__name__)


class IONOSPublisherError(Exception):
    """Raised when roster publishing to IONOS fails with a safe message."""


def _load_sftp_config(secret_name: str, aws_region: str | None) -> dict[str, Any]:
    if not secret_name.strip():
        raise IONOSPublisherError("IONOS SFTP secret name is not configured.")

    try:
        client = boto3.client("secretsmanager", region_name=aws_region)
        response = client.get_secret_value(SecretId=secret_name)
    except (BotoCoreError, ClientError) as exc:
        raise IONOSPublisherError("Unable to fetch IONOS SFTP secret from AWS Secrets Manager.") from exc

    secret_string = response.get("SecretString")
    if not secret_string:
        raise IONOSPublisherError("IONOS SFTP secret is empty or binary and cannot be used.")

    try:
        raw_config = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise IONOSPublisherError("IONOS SFTP secret is not valid JSON.") from exc

    required_fields = ("host", "username", "remote_dir", "remote_filename")
    for field_name in required_fields:
        value = raw_config.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise IONOSPublisherError(f"IONOS SFTP secret is missing required field: {field_name}.")

    port = raw_config.get("port", 22)
    if not isinstance(port, int):
        raise IONOSPublisherError("IONOS SFTP secret field 'port' must be an integer.")

    password = raw_config.get("password")
    if not isinstance(password, str) or not password:
        raise IONOSPublisherError("IONOS SFTP secret is missing required field: password.")

    return {
        "host": raw_config["host"].strip(),
        "port": port,
        "username": raw_config["username"].strip(),
        "password": password,
        "remote_dir": raw_config["remote_dir"].strip(),
        "remote_filename": raw_config["remote_filename"].strip(),
        "secret_keys": tuple(sorted(raw_config.keys())),
    }


def _ensure_remote_dir(sftp: Any, remote_dir: str) -> None:
    normalized_dir = remote_dir.strip("/")
    if not normalized_dir:
        return

    current_dir = ""
    for part in normalized_dir.split("/"):
        if not part:
            continue
        current_dir = f"{current_dir}/{part}" if current_dir else part
        try:
            sftp.chdir(current_dir)
        except IOError:
            sftp.mkdir(current_dir)
            sftp.chdir(current_dir)


def upload_pdf_to_ionos(
    *,
    local_pdf_path: str | Path,
    secret_name: str,
    aws_region: str | None = None,
    remote_path: str | None = None,
) -> dict[str, Any]:
    """Upload one PDF file to IONOS using SFTP credentials from Secrets Manager."""
    if paramiko is None:
        raise IONOSPublisherError(
            "IONOS publish dependency is not installed. Install 'paramiko' to enable SFTP publishing."
        )

    path = Path(local_pdf_path)
    if not path.exists() or not path.is_file():
        raise IONOSPublisherError(f"Local PDF file does not exist: {path}")

    config = _load_sftp_config(secret_name=secret_name, aws_region=aws_region)
    resolved_remote_path = remote_path or posixpath.join(
        config["remote_dir"].strip("/"),
        config["remote_filename"],
    )
    remote_dir = posixpath.dirname(resolved_remote_path) or "/"

    transport = None
    sftp = None
    try:
        transport = paramiko.Transport((config["host"], config["port"]))
        transport.connect(username=config["username"], password=config["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.stat(remote_dir)
        except Exception as exc:
            logger.warning(
                "IONOS remote directory check failed: remote_dir=%s error=%s",
                remote_dir,
                exc.__class__.__name__,
            )
            raise
        sftp.put(str(path), resolved_remote_path)
    except paramiko.SSHException as exc:
        raise IONOSPublisherError("Unable to upload short roster PDF to IONOS via SFTP.") from exc
    except OSError as exc:
        raise IONOSPublisherError("Unable to upload short roster PDF to IONOS due to a file or network error.") from exc
    finally:
        if sftp is not None:
            sftp.close()
        if transport is not None:
            transport.close()

    return {"uploaded": True, "remote_path": resolved_remote_path}
