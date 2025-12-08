import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from config import settings


@dataclass
class StoredVideo:
    """Metadata for a stored video"""
    session_id: str
    filename: str
    url: str
    size_bytes: int
    storage_type: str  # "local" or "google_drive"


class StorageStrategy(ABC):
    """Abstract base class for storage strategies"""

    @abstractmethod
    def upload_video(self, session_id: str, file_path: str, filename: str) -> StoredVideo:
        """Upload video and return metadata with URL/path"""
        pass

    @abstractmethod
    def download_video(self, session_id: str, filename: str) -> bytes:
        """Download video bytes"""
        pass

    @abstractmethod
    def get_video_url(self, session_id: str, filename: str) -> str:
        """Get accessible URL for video"""
        pass

    @abstractmethod
    def list_session_videos(self, session_id: str) -> List[StoredVideo]:
        """List all videos in a session"""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete all videos for a session"""
        pass

    @abstractmethod
    def delete_video(self, session_id: str, filename: str) -> bool:
        """Delete a specific video"""
        pass


class LocalStorageStrategy(StorageStrategy):
    """Local filesystem storage for MVP/development"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """Get path for session folder"""
        path = self.base_path / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def upload_video(self, session_id: str, file_path: str, filename: str) -> StoredVideo:
        """Copy video to session folder"""
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        dest_dir = self._get_session_path(session_id)
        dest_path = dest_dir / filename

        # Copy file
        shutil.copy2(source, dest_path)

        return StoredVideo(
            session_id=session_id,
            filename=filename,
            url=str(dest_path),
            size_bytes=dest_path.stat().st_size,
            storage_type="local"
        )

    def download_video(self, session_id: str, filename: str) -> bytes:
        """Read video bytes from local storage"""
        file_path = self._get_session_path(session_id) / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Video not found: {file_path}")
        return file_path.read_bytes()

    def get_video_url(self, session_id: str, filename: str) -> str:
        """Return local file path as URL"""
        return str(self._get_session_path(session_id) / filename)

    def list_session_videos(self, session_id: str) -> List[StoredVideo]:
        """List all videos in session folder"""
        session_path = self._get_session_path(session_id)
        videos = []
        for file_path in session_path.glob("*.mp4"):
            videos.append(StoredVideo(
                session_id=session_id,
                filename=file_path.name,
                url=str(file_path),
                size_bytes=file_path.stat().st_size,
                storage_type="local"
            ))
        return videos

    def delete_session(self, session_id: str) -> bool:
        """Delete entire session folder"""
        session_path = self.base_path / session_id
        if session_path.exists():
            shutil.rmtree(session_path)
            return True
        return False

    def delete_video(self, session_id: str, filename: str) -> bool:
        """Delete specific video file"""
        file_path = self._get_session_path(session_id) / filename
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class GoogleDriveStorageStrategy(StorageStrategy):
    """Google Drive storage for production"""

    def __init__(self, folder_id: str, service_account_file: str):
        self.folder_id = folder_id
        self.service_account_file = service_account_file
        self._service = None

    @property
    def service(self):
        """Lazy-load Google Drive service"""
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            self._service = build("drive", "v3", credentials=credentials)
        return self._service

    def _get_or_create_session_folder(self, session_id: str) -> str:
        """Get or create a subfolder for the session"""
        # Search for existing folder
        query = (
            f"name='{session_id}' and "
            f"'{self.folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if files:
            return files[0]["id"]

        # Create new folder
        folder_metadata = {
            "name": session_id,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.folder_id]
        }
        folder = self.service.files().create(
            body=folder_metadata,
            fields="id"
        ).execute()
        return folder["id"]

    def upload_video(self, session_id: str, file_path: str, filename: str) -> StoredVideo:
        """Upload video to Google Drive session folder"""
        from googleapiclient.http import MediaFileUpload

        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        # Get/create session folder
        session_folder_id = self._get_or_create_session_folder(session_id)

        # Upload file
        file_metadata = {
            "name": filename,
            "parents": [session_folder_id]
        }
        media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,size"
        ).execute()

        # Make file publicly accessible via link
        self.service.permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"}
        ).execute()

        # Get shareable link
        video_url = f"https://drive.google.com/uc?id={file['id']}&export=download"

        return StoredVideo(
            session_id=session_id,
            filename=filename,
            url=video_url,
            size_bytes=int(file.get("size", 0)),
            storage_type="google_drive"
        )

    def download_video(self, session_id: str, filename: str) -> bytes:
        """Download video from Google Drive"""
        from googleapiclient.http import MediaIoBaseDownload
        import io

        # Find file
        session_folder_id = self._get_or_create_session_folder(session_id)
        query = f"name='{filename}' and '{session_folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if not files:
            raise FileNotFoundError(f"Video not found: {filename}")

        file_id = files[0]["id"]

        # Download
        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue()

    def get_video_url(self, session_id: str, filename: str) -> str:
        """Get shareable Google Drive URL"""
        session_folder_id = self._get_or_create_session_folder(session_id)
        query = f"name='{filename}' and '{session_folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if not files:
            raise FileNotFoundError(f"Video not found: {filename}")

        file_id = files[0]["id"]
        return f"https://drive.google.com/uc?id={file_id}&export=download"

    def list_session_videos(self, session_id: str) -> List[StoredVideo]:
        """List all videos in session folder"""
        session_folder_id = self._get_or_create_session_folder(session_id)
        query = f"'{session_folder_id}' in parents and mimeType='video/mp4' and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id,name,size)"
        ).execute()

        videos = []
        for file in results.get("files", []):
            videos.append(StoredVideo(
                session_id=session_id,
                filename=file["name"],
                url=f"https://drive.google.com/uc?id={file['id']}&export=download",
                size_bytes=int(file.get("size", 0)),
                storage_type="google_drive"
            ))
        return videos

    def delete_session(self, session_id: str) -> bool:
        """Delete session folder from Google Drive"""
        query = (
            f"name='{session_id}' and "
            f"'{self.folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if files:
            self.service.files().delete(fileId=files[0]["id"]).execute()
            return True
        return False

    def delete_video(self, session_id: str, filename: str) -> bool:
        """Delete specific video from Google Drive"""
        session_folder_id = self._get_or_create_session_folder(session_id)
        query = f"name='{filename}' and '{session_folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if files:
            self.service.files().delete(fileId=files[0]["id"]).execute()
            return True
        return False


class StorageManager:
    """Factory class for storage strategy selection"""

    def __init__(self, storage_mode: Optional[str] = None):
        """
        Initialize storage manager.

        Args:
            storage_mode: "local" or "google_drive". Defaults to settings.storage_mode
        """
        mode = storage_mode or settings.storage_mode

        if mode == "local":
            self.strategy = LocalStorageStrategy(settings.storage_path)
        elif mode == "google_drive":
            if not settings.google_drive_folder_id:
                raise ValueError("GOOGLE_DRIVE_FOLDER_ID not set")
            self.strategy = GoogleDriveStorageStrategy(
                folder_id=settings.google_drive_folder_id,
                service_account_file=settings.google_service_account_file
            )
        else:
            raise ValueError(f"Unknown storage mode: {mode}")

        self.mode = mode

    def upload_video(self, session_id: str, file_path: str, filename: str) -> StoredVideo:
        """Upload video using configured strategy"""
        return self.strategy.upload_video(session_id, file_path, filename)

    def download_video(self, session_id: str, filename: str) -> bytes:
        """Download video using configured strategy"""
        return self.strategy.download_video(session_id, filename)

    def get_video_url(self, session_id: str, filename: str) -> str:
        """Get video URL using configured strategy"""
        return self.strategy.get_video_url(session_id, filename)

    def list_session_videos(self, session_id: str) -> List[StoredVideo]:
        """List session videos using configured strategy"""
        return self.strategy.list_session_videos(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete session using configured strategy"""
        return self.strategy.delete_session(session_id)

    def delete_video(self, session_id: str, filename: str) -> bool:
        """Delete video using configured strategy"""
        return self.strategy.delete_video(session_id, filename)


# Default instance using settings
storage_manager = StorageManager()
