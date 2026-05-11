from __future__ import annotations

import os
from pathlib import Path

from financial_system.config import DB_PATH


def _bucket_config() -> tuple[str | None, str]:
    bucket_name = os.getenv("GCS_BUCKET_NAME") or None
    prefix = os.getenv("GCS_REPORT_PREFIX", "daily_reports/").strip("/")
    return bucket_name, prefix


def _storage_client():
    try:
        from google.cloud import storage
    except ImportError:
        return None
    return storage.Client()


def restore_database_from_gcs() -> str:
    bucket_name, prefix = _bucket_config()
    if not bucket_name:
        return "disabled"
    try:
        client = _storage_client()
        if client is None:
            return "disabled: google-cloud-storage not installed"

        object_name = os.getenv("GCS_DB_OBJECT") or f"{prefix}/financial_data.db"
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        if not blob.exists():
            return f"missing: gs://{bucket_name}/{object_name}"

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(DB_PATH))
        return f"restored: gs://{bucket_name}/{object_name}"
    except Exception as exc:
        return f"failed: {exc}"


def backup_database_to_gcs() -> str:
    bucket_name, prefix = _bucket_config()
    if not bucket_name:
        return "disabled"
    if not DB_PATH.exists():
        return "skipped: database missing"
    try:
        client = _storage_client()
        if client is None:
            return "disabled: google-cloud-storage not installed"

        object_name = os.getenv("GCS_DB_OBJECT") or f"{prefix}/financial_data.db"
        bucket = client.bucket(bucket_name)
        bucket.blob(object_name).upload_from_filename(str(DB_PATH))
        return f"uploaded: gs://{bucket_name}/{object_name}"
    except Exception as exc:
        return f"failed: {exc}"


def upload_report_to_gcs(report_path: Path, day: str) -> str:
    bucket_name, prefix = _bucket_config()
    if not bucket_name:
        return "disabled"
    if not report_path.exists():
        return "skipped: report missing"
    try:
        client = _storage_client()
        if client is None:
            return "disabled: google-cloud-storage not installed"

        object_name = f"{prefix}/daily_report_{day}.md"
        bucket = client.bucket(bucket_name)
        bucket.blob(object_name).upload_from_filename(str(report_path), content_type="text/markdown")
        return f"uploaded: gs://{bucket_name}/{object_name}"
    except Exception as exc:
        return f"failed: {exc}"
