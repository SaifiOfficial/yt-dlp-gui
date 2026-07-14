from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DownloadStatus(Enum):
    PENDING = auto()
    EXTRACTING = auto()
    QUEUED = auto()
    DOWNLOADING = auto()
    PAUSED = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()


class FormatType(Enum):
    VIDEO_AUDIO = auto()
    VIDEO_ONLY = auto()
    AUDIO_ONLY = auto()
    OTHER = auto()


@dataclass
class FormatInfo:
    format_id: str
    ext: str
    resolution: str
    filesize: str
    tbr: str
    codec: str
    note: str
    fmt_type: FormatType = FormatType.OTHER


@dataclass
class PlaylistEntry:
    url: str
    title: str
    selected: bool = True
    duration: Optional[int] = None


@dataclass
class DownloadItem:
    url: str
    title: str = ''
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    speed: str = ''
    eta: str = ''
    selected_format: Optional[str] = None
    formats: list[FormatInfo] = field(default_factory=list)
    playlist_entries: list[PlaylistEntry] = field(default_factory=list)
    thumbnail_url: str = ''
    duration: Optional[int] = None
    uploader: str = ''
    error_message: str = ''
    output_path: str = ''
    output_paths: list[str] = field(default_factory=list)
    output_dir: str = ''
    output_format: str = ''
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
