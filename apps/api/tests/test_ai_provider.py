import pytest

from app.services.ai_provider import LocalAIProvider, SarvamAIProvider


class TestLocalAIProvider:
    def setup_method(self):
        self.provider = LocalAIProvider()

    def test_transcribe_audio_returns_placeholder(self):
        result = self.provider.transcribe_audio(b"fake audio")
        assert "not available" in result.transcript
        assert isinstance(result.confidence, float)

    def test_translate_is_noop(self):
        text = "paani nahi aa raha"
        assert self.provider.translate_text(text, "en") == text

    def test_extract_grievance_water(self):
        result = self.provider.extract_grievance(
            "ward 8 mein paani nahi aa raha"
        )
        assert result.category == "water_supply"
        assert result.department == "water_department"
        assert result.ward == "8"

    def test_extract_grievance_redacts_pii(self):
        result = self.provider.extract_grievance(
            "Mera phone 9876543210 hai, ward 5 mein paani nahi"
        )
        assert "9876543210" not in result.pii_redacted_text
        assert "[PHONE_REDACTED]" in result.pii_redacted_text

    def test_generate_draft_includes_all_fields(self):
        context = {
            "title": "Water shortage",
            "department": "water_department",
            "area": "Ward 8",
            "grievance_count": 23,
            "summary": "No water supply for 4 days.",
        }
        draft = self.provider.generate_draft(context)
        assert "Water shortage" in draft
        assert "Water_Department" in draft
        assert "Ward 8" in draft
        assert "23" in draft
        assert "4 days" in draft


class TestSarvamAIProvider:
    def test_requires_api_key(self):
        with pytest.raises(NotImplementedError, match="SARVAM_API_KEY"):
            SarvamAIProvider()
