"""Audio storage service — local filesystem MVP.

Store and retrieve audio files under a date-organised directory tree.
Interface is abstract enough for a future S3 swap: a different backend
can implement save_audio / load_audio / delete_audio with the same
signatures without changing callers.
"""

import os
import uuid
from datetime import date
from typing import Optional

from app.config import get_settings


# ── Extension mapping ─────────────────────────────────────────────────

_CONTENT_TYPE_TO_EXT = {
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
}

_DEFAULT_EXT = ".bin"


def _ext_from_content_type(content_type: str) -> str:
    """Derive a file extension from a MIME content-type string.

    Strips parameters (e.g. ``; charset=utf-8``) before lookup.
    """
    mime = content_type.split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_TO_EXT.get(mime, _DEFAULT_EXT)


# ── AudioStorage ──────────────────────────────────────────────────────


class AudioStorage:
    """Filesystem-backed audio storage.

    Parameters
    ----------
    storage_dir : str or None
        Root directory for stored audio.  If ``None``, reads
        ``AUDIO_STORAGE_DIR`` from application settings (default
        ``"data/audio"``).
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            settings = get_settings()
            storage_dir = settings.audio_storage_dir
        self._root = os.path.abspath(storage_dir)

    # ── public API ────────────────────────────────────────────────

    def save_audio(self, audio_bytes: bytes, content_type: str) -> str:
        """Persist *audio_bytes* and return a storage key (relative path).

        The key has the form ``<yyyy-mm-dd>/<uuid>.<ext>`` where *ext*
        is derived from *content_type*.
        """
        ext = _ext_from_content_type(content_type)
        today = date.today().isoformat()  # yyyy-mm-dd
        filename = f"{uuid.uuid4()}{ext}"
        key = os.path.join(today, filename)

        full_path = os.path.join(self._root, key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(audio_bytes)

        return key

    def load_audio(self, key: str) -> bytes:
        """Load audio bytes for *key*.

        Raises
        ------
        FileNotFoundError
            If no file exists at *key*.
        """
        full_path = os.path.join(self._root, key)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Audio file not found: {key}")
        with open(full_path, "rb") as f:
            return f.read()

    def delete_audio(self, key: str) -> None:
        """Delete the audio file at *key*.

        No-op if the file does not exist — never raises.
        """
        full_path = os.path.join(self._root, key)
        try:
            os.remove(full_path)
        except FileNotFoundError:
            pass
