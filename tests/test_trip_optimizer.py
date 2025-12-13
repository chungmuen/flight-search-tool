#!/usr/bin/env python3
"""
Unit tests for TripOptimizer
"""

import unittest
from datetime import datetime

from trip_finder.trip_finder import TripOptimizer
from trip_finder.google_flights_scraper import Flight


class TestTripOptimizer(unittest.TestCase):
    """Test cases for TripOptimizer"""

    def setUp(self):
        """Set up test fixtures"""
        self.optimizer = TripOptimizer(min_stopover1_days=4, min_stopover2_days=10)

    def test_initialization(self):
        """Test optimizer initialization with custom parameters"""
        optimizer = TripOptimizer(min_stopover1_days=5, min_stopover2_days=12)
        self.assertEqual(optimizer.min_stopover1_days, 5)
        self.assertEqual(optimizer.min_stopover2_days, 12)

    def test_validate_dates_valid_sequence(self):
        """Test date validation with valid sequence"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-10",  # 5 days at stopover1
            seg3_date="2026-02-21",  # 11 days at stopover2
            seg4_date="2026-02-26"
        )
        self.assertTrue(result)

    def test_validate_dates_exact_minimum(self):
        """Test date validation with exact minimum stays"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-09",  # Exactly 4 days
            seg3_date="2026-02-19",  # Exactly 10 days
            seg4_date="2026-02-26"
        )
        self.assertTrue(result)

    def test_validate_dates_insufficient_stopover1(self):
        """Test rejection when stopover1 stay is too short"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-08",  # Only 3 days (need 4)
            seg3_date="2026-02-19",
            seg4_date="2026-02-26"
        )
        self.assertFalse(result)

    def test_validate_dates_insufficient_stopover2(self):
        """Test rejection when stopover2 stay is too short"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-10",
            seg3_date="2026-02-19",  # Only 9 days (need 10)
            seg4_date="2026-02-26"
        )
        self.assertFalse(result)

    def test_validate_dates_wrong_order(self):
        """Test rejection when dates are out of order"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-10",
            seg2_date="2026-02-05",  # Before seg1
            seg3_date="2026-02-20",
            seg4_date="2026-02-25"
        )
        self.assertFalse(result)

    def test_validate_dates_same_dates(self):
        """Test rejection when dates are the same"""
        result = self.optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-05",  # Same as seg1
            seg3_date="2026-02-20",
            seg4_date="2026-02-25"
        )
        self.assertFalse(result)

    def test_find_best_combinations_simple(self):
        """Test finding best combinations with simple dataset"""
        # Create sample flights
        seg1 = [
            Flight("LHR", "HKG", "2026-02-05", 500.0, "BA", "10:00", "18:00", "12h", 0)
        ]
        seg2 = [
            Flight("HKG", "TPE", "2026-02-10", 100.0, "CX", "08:00", "10:00", "2h", 0)
        ]
        seg3 = [
            Flight("TPE", "HKG", "2026-02-21", 120.0, "CX", "14:00", "16:00", "2h", 0)
        ]
        seg4 = [
            Flight("HKG", "LHR", "2026-02-26", 480.0, "BA", "20:00", "06:00+1", "13h", 0)
        ]

        combos = self.optimizer.find_best_combinations(seg1, seg2, seg3, seg4, top_n=10)

        self.assertEqual(len(combos), 1)
        self.assertEqual(combos[0][4], 1200.0)  # Total price

    def test_find_best_combinations_multiple_options(self):
        """Test finding best combinations with multiple flight options"""
        seg1 = [
            Flight("LHR", "HKG", "2026-02-05", 500.0, "BA", "10:00", "18:00", "12h", 0),
            Flight("LHR", "HKG", "2026-02-06", 450.0, "BA", "10:00", "18:00", "12h", 0),
        ]
        seg2 = [
            Flight("HKG", "TPE", "2026-02-10", 100.0, "CX", "08:00", "10:00", "2h", 0),
            Flight("HKG", "TPE", "2026-02-11", 90.0, "CX", "08:00", "10:00", "2h", 0),
        ]
        seg3 = [
            Flight("TPE", "HKG", "2026-02-21", 120.0, "CX", "14:00", "16:00", "2h", 0),
        ]
        seg4 = [
            Flight("HKG", "LHR", "2026-02-26", 480.0, "BA", "20:00", "06:00+1", "13h", 0),
        ]

        combos = self.optimizer.find_best_combinations(seg1, seg2, seg3, seg4, top_n=10)

        # Should find valid combinations
        self.assertGreater(len(combos), 0)
        # Should be sorted by price
        if len(combos) > 1:
            self.assertLessEqual(combos[0][4], combos[1][4])

    def test_find_best_combinations_empty_segments(self):
        """Test handling of empty flight segments"""
        seg1 = []
        seg2 = [Flight("HKG", "TPE", "2026-02-10", 100.0, "CX", "08:00", "10:00", "2h", 0)]
        seg3 = [Flight("TPE", "HKG", "2026-02-21", 120.0, "CX", "14:00", "16:00", "2h", 0)]
        seg4 = [Flight("HKG", "LHR", "2026-02-26", 480.0, "BA", "20:00", "06:00+1", "13h", 0)]

        combos = self.optimizer.find_best_combinations(seg1, seg2, seg3, seg4, top_n=10)

        self.assertEqual(len(combos), 0)


class TestTripOptimizerEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def test_zero_minimum_days(self):
        """Test optimizer with zero minimum stay requirements"""
        optimizer = TripOptimizer(min_stopover1_days=0, min_stopover2_days=0)

        result = optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-02-05",  # Same day - 0 days stay
            seg3_date="2026-02-05",
            seg4_date="2026-02-05"
        )
        # Should fail because dates must be strictly increasing
        self.assertFalse(result)

    def test_large_minimum_days(self):
        """Test optimizer with large minimum stay requirements"""
        optimizer = TripOptimizer(min_stopover1_days=30, min_stopover2_days=60)

        result = optimizer.validate_dates(
            seg1_date="2026-02-05",
            seg2_date="2026-03-10",  # 33 days
            seg3_date="2026-05-15",  # 66 days
            seg4_date="2026-05-20"
        )
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
