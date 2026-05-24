"""Tests for audio storage service — no real audio files needed."""

import os
import pytest

from app.services.audio_storage import AudioStorage


FAKE_AUDIO = bytes(b"fake audio data")


class TestAudioStorage:
    """Test suite for AudioStorage using a temp directory for isolation."""

    def test_save_returns_key_string(self, tmp_path):
        """save_audio returns a storage key (relative path string)."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        assert isinstance(key, str)
        assert len(key) > 0

    def test_save_and_load_roundtrip(self, tmp_path):
        """Save + load roundtrip returns the same bytes."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        loaded = storage.load_audio(key)
        assert loaded == FAKE_AUDIO

    def test_load_nonexistent_key_raises(self, tmp_path):
        """load on nonexistent key raises FileNotFoundError."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            storage.load_audio("nonexistent/key.bin")

    def test_delete_removes_file(self, tmp_path):
        """delete removes file; load after delete raises FileNotFoundError."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        storage.load_audio(key)  # should succeed
        storage.delete_audio(key)
        with pytest.raises(FileNotFoundError):
            storage.load_audio(key)

    def test_delete_nonexistent_key_no_error(self, tmp_path):
        """delete on nonexistent key does not raise."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        storage.delete_audio("nonexistent/key.bin")  # no-op, no error

    def test_content_type_wav_extension(self, tmp_path):
        """content_type 'audio/wav' yields .wav extension on the key."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        _, ext = os.path.splitext(key)
        assert ext == ".wav"

    def test_content_type_mp3_extension(self, tmp_path):
        """content_type 'audio/mp3' yields .mp3 extension on the key."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/mp3")
        _, ext = os.path.splitext(key)
        assert ext == ".mp3"

    def test_content_type_mp4_extension(self, tmp_path):
        """content_type 'audio/mp4' yields .m4a extension on the key."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/mp4")
        _, ext = os.path.splitext(key)
        assert ext == ".m4a"

    def test_content_type_unknown_defaults_to_bin(self, tmp_path):
        """Unknown content_type yields .bin extension as default."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/ogg")
        _, ext = os.path.splitext(key)
        # ogg isn't in the known map, so it should default to .bin
        assert ext == ".bin"

    def test_content_type_with_charset(self, tmp_path):
        """content_type with charset (e.g. 'audio/wav; charset=utf-8') works."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav; charset=utf-8")
        _, ext = os.path.splitext(key)
        assert ext == ".wav"

    def test_save_creates_directory(self, tmp_path):
        """save_audio creates the date-based directory if it doesn't exist."""
        storage_dir = tmp_path / "nested" / "audio"
        storage = AudioStorage(storage_dir=str(storage_dir))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        full_path = os.path.join(str(storage_dir), key)
        assert os.path.isfile(full_path)

    def test_key_uses_date_prefix(self, tmp_path):
        """Storage key includes the date in yyyy-mm-dd format."""
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        # Should start with something like "2026-05-25/"
        parts = key.split("/")
        assert len(parts) == 2
        date_part = parts[0]
        assert len(date_part) == 10  # yyyy-mm-dd
        year, month, day = date_part.split("-")
        assert len(year) == 4
        assert len(month) == 2
        assert len(day) == 2

    def test_key_uses_uuid(self, tmp_path):
        """Storage key filename is a UUID."""
        import uuid as uuid_module
        storage = AudioStorage(storage_dir=str(tmp_path))
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        filename = key.split("/")[1]
        name_without_ext = filename.rsplit(".", 1)[0]
        # Should be a valid UUID
        uuid_module.UUID(name_without_ext)  # raises ValueError if not valid

    def test_default_storage_dir_from_config(self, monkeypatch, tmp_path):
        """When no storage_dir is passed, AUDIO_STORAGE_DIR from config is used."""
        monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path))
        from app.config import get_settings
        # Force settings reload with env var
        monkeypatch.setattr(
            "app.services.audio_storage.get_settings",
            lambda: __import__("app.config", fromlist=["Settings"]).Settings(
                AUDIO_STORAGE_DIR=str(tmp_path)
            ),
        )
        storage = AudioStorage()
        key = storage.save_audio(FAKE_AUDIO, "audio/wav")
        full_path = os.path.join(str(tmp_path), key)
        assert os.path.isfile(full_path)
