"""Tests for geocoding — haversine distance, ward and area inference."""

import pytest

from app.services.geocoding import haversine_m, infer_area, infer_ward, ward_disagrees


class TestHaversine:
    def test_same_point_returns_zero(self):
        assert haversine_m(19.043, 72.857, 19.043, 72.857) == 0.0

    def test_known_mumbai_distance(self):
        """~7 km between Khar West and Andheri West."""
        dist = haversine_m(19.043, 72.857, 19.107, 72.856)
        assert 6000 < dist < 8000, f"Expected ~7 km, got {dist:.0f}m"

    def test_large_distance(self):
        """Mumbai to Delhi should be > 1000 km."""
        dist = haversine_m(19.043, 72.857, 28.6139, 77.2090)
        assert dist > 1_000_000

    def test_within_300m_threshold(self):
        """Two points ~200m apart."""
        dist = haversine_m(19.043, 72.857, 19.0448, 72.857)
        assert dist < 300, f"Expected < 300m, got {dist:.0f}m"


class TestWardInference:
    def test_coords_in_ward_8_return_8(self):
        ward = infer_ward(19.043, 72.857)
        assert ward == "8"

    def test_coords_in_ward_4_return_4(self):
        ward = infer_ward(18.995, 72.835)
        assert ward == "4"

    def test_coords_in_ward_11_return_11(self):
        ward = infer_ward(19.107, 72.856)
        assert ward == "11"

    def test_coords_in_ward_2_return_2(self):
        ward = infer_ward(19.028, 72.849)
        assert ward == "2"

    def test_coords_far_from_all_wards_return_none(self):
        ward = infer_ward(28.6139, 77.2090)
        assert ward is None


class TestAreaInference:
    def test_ward_8_returns_khar_west(self):
        assert infer_area(19.043, 72.857) == "Khar West"

    def test_ward_4_returns_byculla(self):
        assert infer_area(18.995, 72.835) == "Byculla"

    def test_ward_11_returns_andheri_west(self):
        assert infer_area(19.107, 72.856) == "Andheri West"

    def test_ward_2_returns_bandra_west(self):
        assert infer_area(19.028, 72.849) == "Bandra West"

    def test_far_coords_return_empty(self):
        assert infer_area(28.6139, 77.2090) == ""


class TestWardDisagrees:
    def test_matching_coords_do_not_disagree(self):
        assert not ward_disagrees("8", 19.043, 72.857)

    def test_far_coords_disagree(self):
        assert ward_disagrees("8", 28.6139, 77.2090)

    def test_unknown_ward_never_disagrees(self):
        assert not ward_disagrees("99", 19.043, 72.857)
