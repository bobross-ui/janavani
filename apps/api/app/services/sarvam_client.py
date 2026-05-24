import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

import httpx


logger = logging.getLogger(__name__)


class SarvamError(Exception):
    pass


class SarvamTimeoutError(SarvamError):
    pass


class SarvamRateLimitError(SarvamError):
    pass


class SarvamClient:
    def __init__(self, api_key: str, base_url: str, timeout: float, max_retries: int):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def post_json(self, path: str, payload: dict) -> dict:
        model = self._string_value(payload.get("model"))
        language = self._first_string_value(
            payload,
            ("language", "language_code", "source_language_code", "target_language_code"),
        )
        byte_size = len(json.dumps(payload).encode("utf-8"))
        return self._post(
            path=path,
            model=model,
            language=language,
            byte_size=byte_size,
            request_kwargs={"json": payload},
        )

    def post_multipart(self, path: str, files: dict, data: dict) -> dict:
        model = self._string_value(data.get("model"))
        language = self._first_string_value(data, ("language", "language_code"))
        byte_size = self._multipart_byte_size(files)
        return self._post(
            path=path,
            model=model,
            language=language,
            byte_size=byte_size,
            request_kwargs={"files": files, "data": data},
        )

    def post_audio_bytes(self, path: str, audio_bytes: bytes, model: str, language: str) -> dict:
        files = {
            "file": ("audio.wav", audio_bytes, "application/octet-stream"),
        }
        data = {
            "model": model,
            "language_code": language,
        }
        return self._post(
            path=path,
            model=model,
            language=language,
            byte_size=len(audio_bytes),
            request_kwargs={"files": files, "data": data},
        )

    def _post(
        self,
        path: str,
        model: Optional[str],
        language: Optional[str],
        byte_size: int,
        request_kwargs: Dict[str, Any],
    ) -> dict:
        attempts = self.max_retries + 1
        retry_count = 0
        started = time.monotonic()
        last_status = "error"

        for attempt in range(attempts):
            try:
                response = self._client.post(
                    path,
                    headers=self._auth_headers(path),
                    **request_kwargs
                )
                last_status = str(response.status_code)

                if response.status_code == 429:
                    self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                    raise SarvamRateLimitError("Sarvam request failed with status 429")

                if 400 <= response.status_code < 500:
                    self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                    raise SarvamError(
                        "Sarvam request failed with status %s" % response.status_code
                    )

                if 500 <= response.status_code:
                    if attempt < self.max_retries:
                        retry_count += 1
                        self._sleep_before_retry(retry_count)
                        continue
                    self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                    raise SarvamError(
                        "Sarvam request failed with status %s" % response.status_code
                    )

                try:
                    result = self._parse_json(response)
                except SarvamError:
                    self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                    raise
                self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                return result
            except httpx.TimeoutException:
                last_status = "timeout"
                if attempt < self.max_retries:
                    retry_count += 1
                    self._sleep_before_retry(retry_count)
                    continue
                self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                raise SarvamTimeoutError("Sarvam request timeout")
            except SarvamError:
                raise
            except httpx.HTTPError as exc:
                last_status = "transport_error"
                if attempt < self.max_retries:
                    retry_count += 1
                    self._sleep_before_retry(retry_count)
                    continue
                self._log_call(path, model, language, started, last_status, retry_count, byte_size)
                raise SarvamError("Sarvam request failed: %s" % exc.__class__.__name__)

        self._log_call(path, model, language, started, last_status, retry_count, byte_size)
        raise SarvamError("Sarvam request failed")

    def _auth_headers(self, path: str) -> Dict[str, str]:
        # Sarvam endpoints primarily use api-subscription-key. Keep this isolated so
        # endpoint-specific auth differences can be handled here without scattering
        # header construction throughout the app.
        return {"api-subscription-key": self.api_key}

    def _parse_json(self, response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            raise SarvamError("Sarvam response was not valid JSON")
        if not isinstance(data, dict):
            raise SarvamError("Sarvam response JSON was not an object")
        return data

    def _log_call(
        self,
        path: str,
        model: Optional[str],
        language: Optional[str],
        started: float,
        status: str,
        retry_count: int,
        byte_size: int,
    ) -> None:
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "sarvam_call endpoint=%s model=%s language=%s latency_ms=%s status=%s retry_count=%s byte_size=%s",
            self._log_endpoint(path),
            model or "",
            language or "",
            latency_ms,
            status,
            retry_count,
            byte_size,
        )

    def _sleep_before_retry(self, retry_count: int) -> None:
        time.sleep(min(0.1 * (2 ** (retry_count - 1)), 1.0))

    def _log_endpoint(self, path: str) -> str:
        return urlsplit(path).path or path.split("?", 1)[0]

    def _first_string_value(self, data: dict, keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            value = self._string_value(data.get(key))
            if value:
                return value
        return None

    def _string_value(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value
        return None

    def _multipart_byte_size(self, files: dict) -> int:
        total = 0
        for value in files.values():
            file_value = value
            if isinstance(value, tuple) and len(value) >= 2:
                file_value = value[1]
            if isinstance(file_value, bytes):
                total += len(file_value)
        return total
