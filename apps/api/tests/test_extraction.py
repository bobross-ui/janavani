from app.services.extraction import extract_grievance


class TestExtractGrievance:
    def test_hindi_water_ward_8(self):
        result = extract_grievance(
            "हमारे वार्ड 8 में तीन दिन से पानी नहीं आ रहा है", "hi"
        )
        assert result.category == "water_supply"
        assert result.department == "water_department"
        assert result.ward == "8"
        assert result.urgency == "high"

    def test_hinglish_garbage(self):
        result = extract_grievance(
            "ward 11 mein kachra nahi uth raha", "hi-Latn"
        )
        assert result.category == "sanitation"
        assert result.department == "sanitation_department"
        assert result.ward == "11"

    def test_road_pothole_english(self):
        result = extract_grievance(
            "there is a big pothole on the main road near ward 4", "en"
        )
        assert result.category == "roads"
        assert result.department == "public_works"

    def test_electricity_hindi(self):
        result = extract_grievance(
            "वार्ड 2 में कल से बिजली नहीं आ रही", "hi"
        )
        assert result.category == "electricity"
        assert result.ward == "2"

    def test_category_other_when_no_keyword_match(self):
        result = extract_grievance("something random here", "en")
        assert result.category == "other"
        assert result.department == "general_admin"

    def test_ward_not_present_returns_empty(self):
        result = extract_grievance("paani nahi aa raha", "hi-Latn")
        assert result.category == "water_supply"
        assert result.ward == ""

    def test_normalizes_whitespace(self):
        result = extract_grievance(
            "  ward   8   mein   paani   nahi  ", "hi-Latn"
        )
        assert result.normalized_text == "ward 8 mein paani nahi"

    def test_language_preserved(self):
        result = extract_grievance("ward 5 pani", "mr")
        assert result.language == "mr"
        assert result.category == "water_supply"

    def test_ration_keyword(self):
        result = extract_grievance("ward 3 ration nahi mil raha", "hi-Latn")
        assert result.category == "ration"
        assert result.department == "food_department"

    def test_pension_keyword(self):
        result = extract_grievance("pension nahi aai teen mahine se", "hi-Latn")
        assert result.category == "pension"
        assert result.department == "social_welfare"
        assert result.urgency == "high"
