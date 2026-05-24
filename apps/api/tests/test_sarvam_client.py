import json
import logging

import httpx
import pytest

from app.services import sarvam_client
from app.services.sarvam_client import (
    SarvamClient,
    SarvamError,
    SarvamRateLimitError,
    SarvamTimeoutError,
)


API_KEY = "test-api-key"
BASE_URL = "https://sarvam.example.test"


def build_client(monkeypatch, handler, base_url=BASE_URL, max_retries=1):
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(sarvam_client.httpx, "Client", client_factory)
    return SarvamClient(
        api_key=API_KEY,
        base_url=base_url,
        timeout=1.0,
        max_retries=max_retries,
    )


def test_post_json_happy_path_uses_auth_and_logs_safely(monkeypatch, caplog):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["api-subscription-key"] == API_KEY
        assert request.url == httpx.URL(BASE_URL + "/v1/chat/completions")
        return httpx.Response(200, json={"ok": True})

    client = build_client(monkeypatch, handler)

    with caplog.at_level(logging.INFO):
        result = client.post_json(
            "/v1/chat/completions",
            {"model": "sarvam-m", "prompt": "secret prompt content"},
        )

    assert result == {"ok": True}
    assert len(requests) == 1
    log_text = caplog.text
    assert "/v1/chat/completions" in log_text
    assert "sarvam-m" in log_text
    assert "status=200" in log_text
    assert "retry_count=0" in log_text
    assert API_KEY not in log_text
    assert "secret prompt content" not in log_text
    assert "api-subscription-key" not in log_text
    assert "Authorization" not in log_text


def test_post_json_retries_500_then_succeeds(monkeypatch, caplog):
    monkeypatch.setattr(sarvam_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json={"ok": True})

    client = build_client(monkeypatch, handler)

    with caplog.at_level(logging.INFO):
        result = client.post_json("/v1/test", {"model": "sarvam-m"})

    assert result == {"ok": True}
    assert len(calls) == 2
    assert "retry_count=1" in caplog.text


def test_post_json_logs_and_raises_after_exhausted_5xx_retries(monkeypatch, caplog):
    monkeypatch.setattr(sarvam_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "temporary"})

    client = build_client(monkeypatch, handler, max_retries=2)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SarvamError) as exc_info:
            client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 3
    assert "503" in str(exc_info.value)
    assert "retry_count=2" in caplog.text
    assert "status=503" in caplog.text


def test_transient_transport_error_retries_then_succeeds_with_sanitized_error(monkeypatch):
    monkeypatch.setattr(sarvam_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("connect failed with test-api-key", request=request)
        return httpx.Response(200, json={"ok": True})

    client = build_client(monkeypatch, handler)

    assert client.post_json("/v1/test", {"model": "sarvam-m"}) == {"ok": True}
    assert len(calls) == 2


def test_transient_transport_error_exhaustion_has_sanitized_message(monkeypatch):
    monkeypatch.setattr(sarvam_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.RemoteProtocolError("server said test-api-key", request=request)

    client = build_client(monkeypatch, handler)

    with pytest.raises(SarvamError) as exc_info:
        client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 2
    assert "RemoteProtocolError" in str(exc_info.value)
    assert API_KEY not in str(exc_info.value)


def test_generic_4xx_raises_without_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": "bad request"})

    client = build_client(monkeypatch, handler, max_retries=2)

    with pytest.raises(SarvamError) as exc_info:
        client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 1
    assert "400" in str(exc_info.value)


def test_429_raises_rate_limit_without_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": "rate limited"})

    client = build_client(monkeypatch, handler)

    with pytest.raises(SarvamRateLimitError) as exc_info:
        client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 1
    assert "429" in str(exc_info.value)
    assert API_KEY not in str(exc_info.value)


def test_timeout_maps_to_sarvam_timeout_error_after_retries(monkeypatch):
    monkeypatch.setattr(sarvam_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.TimeoutException("network timeout with no secrets")

    client = build_client(monkeypatch, handler)

    with pytest.raises(SarvamTimeoutError) as exc_info:
        client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 2
    assert "timeout" in str(exc_info.value).lower()
    assert API_KEY not in str(exc_info.value)


def test_malformed_json_response_maps_to_sarvam_error(monkeypatch, caplog):
    def handler(request):
        return httpx.Response(200, content=b"not json")

    client = build_client(monkeypatch, handler)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SarvamError) as exc_info:
            client.post_json("/v1/test", {"model": "sarvam-m"})

    assert "json" in str(exc_info.value).lower()
    assert API_KEY not in str(exc_info.value)
    assert "sarvam_call" in caplog.text
    assert "status=200" in caplog.text


def test_json_array_response_maps_to_sarvam_error_and_logs(monkeypatch, caplog):
    def handler(request):
        return httpx.Response(200, json=[{"ok": True}])

    client = build_client(monkeypatch, handler)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SarvamError) as exc_info:
            client.post_json("/v1/test", {"model": "sarvam-m"})

    assert "object" in str(exc_info.value).lower()
    assert "sarvam_call" in caplog.text
    assert "status=200" in caplog.text


def test_max_retries_zero_makes_single_attempt(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"error": "temporary"})

    client = build_client(monkeypatch, handler, max_retries=0)

    with pytest.raises(SarvamError):
        client.post_json("/v1/test", {"model": "sarvam-m"})

    assert len(calls) == 1


def test_trailing_slash_base_url_and_query_path_logging_is_sanitized(monkeypatch, caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = build_client(monkeypatch, handler, base_url=BASE_URL + "/")

    with caplog.at_level(logging.INFO):
        result = client.post_json(
            "/v1/test?token=secret-query-token",
            {"model": "sarvam-m"},
        )

    sarvam_log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == sarvam_client.__name__
    )
    assert result == {"ok": True}
    assert requests[0].url == httpx.URL(BASE_URL + "/v1/test?token=secret-query-token")
    assert "endpoint=/v1/test" in sarvam_log_text
    assert "secret-query-token" not in sarvam_log_text


def test_post_json_byte_size_uses_json_encoding_not_python_repr(monkeypatch, caplog):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    client = build_client(monkeypatch, handler)
    payload = {"model": "sarvam-m", "enabled": True, "nothing": None}

    with caplog.at_level(logging.INFO):
        client.post_json("/v1/test", payload)

    assert "byte_size=%s" % len(json.dumps(payload).encode("utf-8")) in caplog.text


def test_client_close_closes_owned_httpx_client(monkeypatch):
    client = build_client(monkeypatch, lambda request: httpx.Response(200, json={"ok": True}))

    client.close()

    assert client._client.is_closed


def test_client_context_manager_closes_owned_httpx_client(monkeypatch):
    with build_client(monkeypatch, lambda request: httpx.Response(200, json={"ok": True})) as client:
        assert not client._client.is_closed

    assert client._client.is_closed


def test_post_audio_bytes_sends_model_language_and_bytes_safely(monkeypatch, caplog):
    audio = b"fake audio bytes"
    requests = []

    def handler(request):
        requests.append(request)
        body = request.content
        assert b"saarika:v2.5" in body
        assert b"hi-IN" in body
        assert audio in body
        assert request.headers["api-subscription-key"] == API_KEY
        return httpx.Response(200, json={"transcript": "raw transcript should not log"})

    client = build_client(monkeypatch, handler)

    with caplog.at_level(logging.INFO):
        result = client.post_audio_bytes(
            "/speech-to-text",
            audio_bytes=audio,
            model="saarika:v2.5",
            language="hi-IN",
        )

    assert result == {"transcript": "raw transcript should not log"}
    assert len(requests) == 1
    log_text = caplog.text
    assert "model=saarika:v2.5" in log_text
    assert "language=hi-IN" in log_text
    assert "byte_size=16" in log_text
    assert API_KEY not in log_text
    assert "fake audio bytes" not in log_text
    assert "raw transcript should not log" not in log_text
