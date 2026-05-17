from __future__ import annotations

import os
import shutil
import subprocess

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def ensure_google_credentials(scopes: list[str] | None = None):
    """Return fresh Google credentials before touching Google APIs."""
    scopes = scopes or SHEETS_SCOPES
    try:
        credentials, project_id = google.auth.default(scopes=scopes)
    except DefaultCredentialsError as exc:
        if os.getenv("K_SERVICE") or not shutil.which("gcloud"):
            raise RuntimeError(
                "Google credentials are unavailable. On Cloud Run, attach a service "
                "account with Google Sheets access. Locally, run "
                "`gcloud auth application-default login --scopes=https://www.googleapis.com/auth/spreadsheets`."
            ) from exc

        subprocess.run(
            [
                "gcloud",
                "auth",
                "application-default",
                "login",
                "--scopes=https://www.googleapis.com/auth/spreadsheets",
            ],
            check=True,
        )
        credentials, project_id = google.auth.default(scopes=scopes)

    if not credentials.valid or credentials.expired:
        credentials.refresh(Request())
    return credentials, project_id
