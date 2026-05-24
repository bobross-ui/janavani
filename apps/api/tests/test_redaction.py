from app.services.redaction import (
    redact_aadhaar,
    redact_all,
    redact_emails,
    redact_phone_numbers,
)


class TestRedactPhoneNumbers:
    def test_redact_10_digit_phone(self):
        text = "Mera phone 9876543210 hai"
        result = redact_phone_numbers(text)
        assert "9876543210" not in result
        assert "[PHONE_REDACTED]" in result

    def test_redact_multiple_phones(self):
        text = "Call 9876543210 or 9123456780"
        result = redact_phone_numbers(text)
        assert result.count("[PHONE_REDACTED]") == 2

    def test_no_phone_no_change(self):
        text = "paani nahi aa raha"
        assert redact_phone_numbers(text) == text


class TestRedactAadhaar:
    def test_redact_12_digit_aadhaar(self):
        text = "Aadhaar 123456789012 hai"
        result = redact_aadhaar(text)
        assert "123456789012" not in result
        assert "[ID_REDACTED]" in result

    def test_no_aadhaar_no_change(self):
        text = "ward 5 mein paani nahi"
        assert redact_aadhaar(text) == text


class TestRedactEmails:
    def test_redact_email(self):
        text = "Contact ramu@example.com for details"
        result = redact_emails(text)
        assert "ramu@example.com" not in result
        assert "[EMAIL_REDACTED]" in result


class TestRedactAll:
    def test_redact_phone_and_email(self):
        text = (
            "Mera phone 9876543210 hai, email ramu@test.com, "
            "ward 5 mein paani nahi aa raha"
        )
        result = redact_all(text)
        assert "[PHONE_REDACTED]" in result
        assert "[EMAIL_REDACTED]" in result
        assert "9876543210" not in result
        assert "ramu@test.com" not in result
        assert "ward 5 mein paani nahi aa raha" in result

    def test_no_pii_no_change(self):
        text = "ward 8 mein teen din se paani nahi"
        assert redact_all(text) == text

    def test_short_numbers_not_redacted(self):
        text = "ward 8 mein 3 din se paani nahi"
        result = redact_all(text)
        assert result == text
