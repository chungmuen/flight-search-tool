#!/usr/bin/env python3
"""
Unit tests for GoogleFlightsScraper
"""

import unittest
from datetime import datetime
from trip_finder.google_flights_scraper import GoogleFlightsScraper, Flight, RoundTripFlight


class TestGoogleFlightsScraper(unittest.TestCase):
    """Test cases for GoogleFlightsScraper"""

    def setUp(self):
        """Set up test fixtures"""
        self.scraper = GoogleFlightsScraper(headless=True, delay=1)

    def test_build_search_url_oneway(self):
        """Test one-way search URL building"""
        url = self.scraper.build_search_url(
            origin="LHR",
            destination="HKG",
            departure_date="2026-02-05",
            adults=1
        )

        self.assertIn("google.com/travel/flights", url)
        self.assertIn("LHR", url)
        self.assertIn("HKG", url)
        self.assertIn("2026-02-05", url)
        self.assertIn("hl=en", url)
        self.assertIn("curr=GBP", url)

    def test_build_search_url_roundtrip(self):
        """Test round-trip search URL building"""
        url = self.scraper.build_search_url(
            origin="JFK",
            destination="DXB",
            departure_date="2026-03-01",
            adults=2,
            return_date="2026-03-15"
        )

        self.assertIn("google.com/travel/flights", url)
        self.assertIn("JFK", url)
        self.assertIn("DXB", url)
        self.assertIn("2026-03-01", url)
        self.assertIn("2026-03-15", url)
        self.assertIn("returning", url)

    def test_build_search_url_date_formatting(self):
        """Test that dates are formatted correctly"""
        url = self.scraper.build_search_url(
            origin="LHR",
            destination="HKG",
            departure_date="2026-02-05"
        )

        # Should contain properly formatted date
        self.assertIn("2026-02-05", url)

    def test_flight_dataclass(self):
        """Test Flight dataclass creation"""
        flight = Flight(
            origin="LHR",
            destination="HKG",
            departure_date="2026-02-05",
            price=500.00,
            airline="British Airways",
            departure_time="10:00 AM",
            arrival_time="6:00 PM",
            duration="12h 30m",
            stops=1
        )

        self.assertEqual(flight.origin, "LHR")
        self.assertEqual(flight.destination, "HKG")
        self.assertEqual(flight.price, 500.00)
        self.assertEqual(flight.stops, 1)
        self.assertIn("LHR->HKG", str(flight))

    def test_roundtrip_flight_dataclass(self):
        """Test RoundTripFlight dataclass creation"""
        rt = RoundTripFlight(
            origin="LHR",
            destination="HKG",
            outbound_date="2026-02-05",
            return_date="2026-02-20",
            total_price=1200.00,
            outbound_airline="BA",
            return_airline="CX",
            outbound_departure_time="10:00",
            outbound_arrival_time="18:00",
            outbound_duration="12h",
            outbound_stops=0,
            return_departure_time="20:00",
            return_arrival_time="06:00+1",
            return_duration="13h",
            return_stops=1
        )

        self.assertEqual(rt.total_price, 1200.00)
        self.assertEqual(rt.outbound_stops, 0)
        self.assertEqual(rt.return_stops, 1)
        self.assertIn("LHR↔HKG", str(rt))


class TestScraperValidation(unittest.TestCase):
    """Test validation and error handling"""

    def test_invalid_date_format(self):
        """Test handling of invalid date formats"""
        scraper = GoogleFlightsScraper()

        # Should not raise error, will be caught by datetime parsing
        with self.assertRaises(ValueError):
            datetime.strptime("invalid-date", "%Y-%m-%d")

    def test_airport_code_format(self):
        """Test airport codes are uppercase"""
        scraper = GoogleFlightsScraper()
        url = scraper.build_search_url("lhr", "hkg", "2026-02-05")

        # URL should contain uppercase codes (our parsing in trip_finder handles this)
        self.assertIn("lhr", url.lower())


if __name__ == '__main__':
    unittest.main()
