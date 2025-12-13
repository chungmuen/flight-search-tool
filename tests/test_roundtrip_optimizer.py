#!/usr/bin/env python3
"""
Unit tests for RoundTripOptimizer
"""

import unittest

from trip_finder.trip_finder_roundtrip import RoundTripOptimizer
from trip_finder.google_flights_scraper import RoundTripFlight


class TestRoundTripOptimizer(unittest.TestCase):
    """Test cases for RoundTripOptimizer"""

    def setUp(self):
        """Set up test fixtures"""
        self.optimizer = RoundTripOptimizer(min_stopover1_days=4, min_stopover2_days=10)

    def test_initialization(self):
        """Test optimizer initialization"""
        optimizer = RoundTripOptimizer(min_stopover1_days=5, min_stopover2_days=12)
        self.assertEqual(optimizer.min_stopover1_days, 5)
        self.assertEqual(optimizer.min_stopover2_days, 12)

    def test_validate_dates_valid(self):
        """Test date validation with valid round-trip dates"""
        rt1 = RoundTripFlight(
            origin="LHR", destination="HKG",
            outbound_date="2026-02-05",
            return_date="2026-02-26",
            total_price=1000.0,
            outbound_airline="BA", return_airline="BA",
            outbound_departure_time="10:00", outbound_arrival_time="18:00",
            outbound_duration="12h", outbound_stops=0,
            return_departure_time="20:00", return_arrival_time="06:00+1",
            return_duration="13h", return_stops=0
        )

        rt2 = RoundTripFlight(
            origin="HKG", destination="TPE",
            outbound_date="2026-02-10",  # 5 days after rt1 outbound
            return_date="2026-02-21",    # 11 days stay in Taiwan
            total_price=200.0,
            outbound_airline="CX", return_airline="CX",
            outbound_departure_time="08:00", outbound_arrival_time="10:00",
            outbound_duration="2h", outbound_stops=0,
            return_departure_time="14:00", return_arrival_time="16:00",
            return_duration="2h", return_stops=0
        )

        result = self.optimizer.validate_dates(rt1, rt2)
        self.assertTrue(result)

    def test_validate_dates_insufficient_stopover1(self):
        """Test rejection when stopover1 stay is too short"""
        rt1 = RoundTripFlight(
            "LHR", "HKG", "2026-02-05", "2026-02-26", 1000.0,
            "BA", "BA", "10:00", "18:00", "12h", 0,
            "20:00", "06:00+1", "13h", 0
        )

        rt2 = RoundTripFlight(
            "HKG", "TPE", "2026-02-08", "2026-02-21", 200.0,  # Only 3 days (need 4)
            "CX", "CX", "08:00", "10:00", "2h", 0,
            "14:00", "16:00", "2h", 0
        )

        result = self.optimizer.validate_dates(rt1, rt2)
        self.assertFalse(result)

    def test_validate_dates_insufficient_stopover2(self):
        """Test rejection when stopover2 stay is too short"""
        rt1 = RoundTripFlight(
            "LHR", "HKG", "2026-02-05", "2026-02-26", 1000.0,
            "BA", "BA", "10:00", "18:00", "12h", 0,
            "20:00", "06:00+1", "13h", 0
        )

        rt2 = RoundTripFlight(
            "HKG", "TPE", "2026-02-10", "2026-02-19", 200.0,  # Only 9 days (need 10)
            "CX", "CX", "08:00", "10:00", "2h", 0,
            "14:00", "16:00", "2h", 0
        )

        result = self.optimizer.validate_dates(rt1, rt2)
        self.assertFalse(result)

    def test_validate_dates_wrong_order(self):
        """Test rejection when dates are in wrong chronological order"""
        rt1 = RoundTripFlight(
            "LHR", "HKG", "2026-02-05", "2026-02-15", 1000.0,  # Returns too early
            "BA", "BA", "10:00", "18:00", "12h", 0,
            "20:00", "06:00+1", "13h", 0
        )

        rt2 = RoundTripFlight(
            "HKG", "TPE", "2026-02-10", "2026-02-21", 200.0,  # Conflicts with rt1 return
            "CX", "CX", "08:00", "10:00", "2h", 0,
            "14:00", "16:00", "2h", 0
        )

        result = self.optimizer.validate_dates(rt1, rt2)
        self.assertFalse(result)

    def test_find_best_combinations_simple(self):
        """Test finding best combinations with simple dataset"""
        rt1_list = [
            RoundTripFlight(
                "LHR", "HKG", "2026-02-05", "2026-02-26", 1000.0,
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            )
        ]

        rt2_list = [
            RoundTripFlight(
                "HKG", "TPE", "2026-02-10", "2026-02-21", 200.0,
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            )
        ]

        combos = self.optimizer.find_best_combinations(rt1_list, rt2_list, top_n=10)

        self.assertEqual(len(combos), 1)
        self.assertEqual(combos[0][2], 1200.0)  # Total price

    def test_find_best_combinations_multiple_options(self):
        """Test finding best combinations with multiple options"""
        rt1_list = [
            RoundTripFlight(
                "LHR", "HKG", "2026-02-05", "2026-02-26", 1000.0,
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            ),
            RoundTripFlight(
                "LHR", "HKG", "2026-02-06", "2026-02-27", 950.0,  # Cheaper
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            )
        ]

        rt2_list = [
            RoundTripFlight(
                "HKG", "TPE", "2026-02-10", "2026-02-21", 200.0,
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            ),
            RoundTripFlight(
                "HKG", "TPE", "2026-02-11", "2026-02-22", 180.0,  # Cheaper
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            )
        ]

        combos = self.optimizer.find_best_combinations(rt1_list, rt2_list, top_n=10)

        # Should find valid combinations
        self.assertGreater(len(combos), 0)
        # Should be sorted by price (cheapest first)
        if len(combos) > 1:
            self.assertLessEqual(combos[0][2], combos[1][2])

    def test_find_best_combinations_no_valid(self):
        """Test when no valid combinations exist"""
        rt1_list = [
            RoundTripFlight(
                "LHR", "HKG", "2026-02-05", "2026-02-10", 1000.0,  # Returns too early
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            )
        ]

        rt2_list = [
            RoundTripFlight(
                "HKG", "TPE", "2026-02-08", "2026-02-21", 200.0,  # Overlaps with rt1
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            )
        ]

        combos = self.optimizer.find_best_combinations(rt1_list, rt2_list, top_n=10)

        self.assertEqual(len(combos), 0)

    def test_top_n_limit(self):
        """Test that top_n parameter limits results"""
        rt1_list = [
            RoundTripFlight(
                "LHR", "HKG", "2026-02-05", "2026-02-26", 1000.0,
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            ),
            RoundTripFlight(
                "LHR", "HKG", "2026-02-06", "2026-02-27", 1010.0,
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            ),
            RoundTripFlight(
                "LHR", "HKG", "2026-02-07", "2026-02-28", 1020.0,
                "BA", "BA", "10:00", "18:00", "12h", 0,
                "20:00", "06:00+1", "13h", 0
            )
        ]

        rt2_list = [
            RoundTripFlight(
                "HKG", "TPE", "2026-02-10", "2026-02-21", 200.0,
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            ),
            RoundTripFlight(
                "HKG", "TPE", "2026-02-11", "2026-02-22", 210.0,
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            ),
            RoundTripFlight(
                "HKG", "TPE", "2026-02-12", "2026-02-23", 220.0,
                "CX", "CX", "08:00", "10:00", "2h", 0,
                "14:00", "16:00", "2h", 0
            )
        ]

        combos = self.optimizer.find_best_combinations(rt1_list, rt2_list, top_n=2)

        # Should return at most 2 results
        self.assertLessEqual(len(combos), 2)


if __name__ == '__main__':
    unittest.main()
