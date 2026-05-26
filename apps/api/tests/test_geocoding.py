"""Tests for geocoding — haversine distance and ward inference."""

import pytest

from app.services.geocoding import haversine_m, infer_ward, ward_disagrees


class TestHaversine:
    def test_same_point_returns_zero(self):
        assert haversine_m(19.0760, 72.8777, 19.0760, 72.8777) == 0.0

    def test_known_mumbai_distance(self):
        """~2 km between two approximate Mumbai points."""
        dist = haversine_m(19.0760, 72.8777, 19.0900, 72.8950)
        # Should be roughly 2-5 km
        assert 1000 < dist < 5000, f"Expected ~2-5 km, got {dist:.0f}m"

    def test_large_distance(self):
        """Mumbai to Delhi should be > 1000 km."""
        dist = haversine_m(19.0760, 72.8777, 28.6139, 77.2090)
        assert dist > 1_000_000  # > 1000 km in metres

    def test_within_300m_threshold(self):
        """Two points ~200m apart should be within the default threshold."""
        # Move ~0.0018 degrees (~200m at Mumbai latitude)
        dist = haversine_m(19.0760, 72.8777, 19.0778, 72.8777)
        assert dist < 300, f"Expected < 300m, got {dist:.0f}m"


class TestWardInference:
    def test_coords_in_ward_8_return_8(self):
        ward = infer_ward(19.0700, 72.8800)
        assert ward == "8"

    def test_coords_near_ward_4_return_4(self):
        ward = infer_ward(19.0800, 72.8900)
        assert ward == "4"

    def test_coords_far_from_all_wards_return_none(self):
        # Somewhere in Delhi — no demo ward there
        ward = infer_ward(28.6139, 77.2090)
        assert ward is None

    def test_ward_2_coords_return_2(self):
        ward = infer_ward(19.0760, 72.8777)
        assert ward == "2"

    def test_ward_11_coords_return_11(self):
        ward = infer_ward(19.0900, 72.8950)
        assert ward == "11"


class TestWardDisagrees:
    def test_matching_coords_do_not_disagree(self):
        assert not ward_disagrees("8", 19.0700, 72.8800)

    def test_far_coords_disagree(self):
        # Delhi coords with Ward 8 → disagreement
        assert ward_disagrees("8", 28.6139, 77.2090)

    def test_unknown_ward_never_disagrees(self):
        assert not ward_disagrees("99", 19.0700, 72.8800)
