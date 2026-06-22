"""
gdrive_storage.py — Google Drive JSON storage helper
=====================================================
Replaces local JSON file I/O with Google Drive reads/writes.

SETUP INSTRUCTIONS (do this once):
  1. Go to https://console.cloud.google.com/ and create a project.
  2. Enable the "Google Drive API" for the project.
  3. Create a Service Account (IAM & Admin → Service Accounts).
  4. Create a JSON key for the service account and save it as
     "gdrive_credentials.json" next to this file.
  5. Create a folder in Google Drive. Open it, copy the folder ID
     from the URL (the long string after /folders/).
  6. Share that Drive folder with the service account's email
     (found in gdrive_credentials.json under "client_email").
  7. Set DRIVE_FOLDER_ID below to your folder ID.
  8. Install dependencies:
       pip install google-api-python-client google-auth
"""

import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload, MediaIoBaseDownload

# Path to the service account JSON key file
_CREDENTIALS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gdrive_credentials.json"
)

# The Google Drive folder ID where JSON files will be stored.
DRIVE_FOLDER_ID = "https://drive.google.com/drive/folders/1EFpfHNYcP9qqSQ0AS-pvyka4_9xGLj86"

# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_service = None  # cached Drive API service


def _get_service():
    global _service
    if _service is None:
        if not os.path.exists(_CREDENTIALS_FILE):
            raise FileNotFoundError(
                f"Google Drive credentials file not found: {_CREDENTIALS_FILE}\n"
                "See gdrive_storage.py setup instructions."
            )
        creds = service_account.Credentials.from_service_account_file(
            _CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        _service = build("drive", "v3", credentials=creds)
    return _service


def _find_file_id(filename):
    """Return the Drive file ID for *filename* inside DRIVE_FOLDER_ID, or None."""
    service = _get_service()
    escaped = filename.replace("'", "\\'")
    query = (
        f"name='{escaped}' and trashed=false"
        f" and '{DRIVE_FOLDER_ID}' in parents"
    )
    results = (
        service.files()
        .list(q=query, fields="files(id, name)", pageSize=1)
        .execute()
    )
    files = results.get("files", [])
    return files[0]["id"] if files else None


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def load_json(filename, default=None):
    """
    Download *filename* from Google Drive and return its parsed JSON.
    Returns *default* if the file does not exist on Drive.
    """
    service = _get_service()
    file_id = _find_file_id(filename)
    if file_id is None:
        return default

    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return json.loads(fh.read().decode("utf-8"))


def save_json(filename, data):
    """
    Upload *data* as JSON to Google Drive.
    Creates the file if it does not exist; updates it if it does.
    """
    service = _get_service()
    content = json.dumps(data, indent=4).encode("utf-8")
    media = MediaInMemoryUpload(content, mimetype="application/json", resumable=False)

    file_id = _find_file_id(filename)
    if file_id:
        # Update existing file (don't change parents)
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # Create new file inside the configured folder
        metadata = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
        service.files().create(body=metadata, media_body=media, fields="id").execute()
