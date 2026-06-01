"""POST /tts — text-to-speech endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Response

from app.routes.grievances import get_request_ai_provider
from app.schemas import TTSRequest
from app.services.ai_provider import AIProvider
from app.services.sarvam_client import SarvamError

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("")
def synthesize_text_to_speech(
    body: TTSRequest,
    provider: AIProvider = Depends(get_request_ai_provider),
):
    """Convert text to speech audio (WAV).

    Returns raw audio/wav bytes.

    Defined as a sync endpoint (not ``async``) on purpose: ``synthesize_speech``
    does blocking HTTP I/O, so FastAPI runs this in a threadpool instead of
    stalling the event loop.
    """
    # ── validate text length ────────────────────────────────────
    if len(body.text) > 500:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long: {len(body.text)} characters (max 500)",
        )

    # ── call provider ───────────────────────────────────────────
    try:
        audio_bytes = provider.synthesize_speech(
            body.text,
            language=body.language,
            speaker=body.speaker,
        )
    except SarvamError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TTS service error: {exc}",
        )

    return Response(content=audio_bytes, media_type="audio/wav")
