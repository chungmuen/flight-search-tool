#!/usr/bin/env python3
"""
Google Flights Web Scraper
Scrapes flight data from Google Flights to find best flight combinations
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from playwright.async_api import async_playwright, Page, Browser
import time


@dataclass
class Flight:
    """Represents a flight segment"""
    origin: str
    destination: str
    departure_date: str
    price: float
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: int
    url: str = ""  # Google Flights URL for this search

    def __repr__(self):
        return f"{self.origin}->{self.destination} on {self.departure_date} (£{self.price:.2f})"


@dataclass
class RoundTripFlight:
    """Represents a round-trip flight"""
    origin: str
    destination: str
    outbound_date: str
    return_date: str
    total_price: float
    outbound_airline: str
    return_airline: str
    outbound_departure_time: str
    outbound_arrival_time: str
    outbound_duration: str
    outbound_stops: int
    return_departure_time: str
    return_arrival_time: str
    return_duration: str
    return_stops: int
    url: str = ""  # Google Flights URL for this round-trip search

    def __repr__(self):
        return f"{self.origin}↔{self.destination} ({self.outbound_date} to {self.return_date}) £{self.total_price:.2f}"


class GoogleFlightsScraper:
    """Handles web scraping of Google Flights data"""

    def __init__(self, headless: bool = True, delay: int = 3):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode
            delay: Delay between requests in seconds (to avoid rate limiting)
        """
        self.headless = headless
        self.delay = delay
        self.base_url = "https://www.google.com/travel/flights"
        self.browser: Optional[Browser] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()

    def build_search_url(self, origin: str, destination: str,
                        departure_date: str, adults: int = 1,
                        return_date: str = None) -> str:
        """
        Build Google Flights search URL directly

        Args:
            origin: Origin airport code (e.g., 'LHR')
            destination: Destination airport code (e.g., 'HKG')
            departure_date: Date in YYYY-MM-DD format
            adults: Number of adult passengers
            return_date: Optional return date for round-trip searches (YYYY-MM-DD format)

        Returns:
            Complete Google Flights search URL
        """
        # Build direct search URL - more reliable than form filling
        # Format: /travel/flights/search?tfs=...
        # We'll use the simple query parameter approach
        from datetime import datetime

        date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y-%m-%d")

        if return_date:
            # Round trip search
            return_obj = datetime.strptime(return_date, "%Y-%m-%d")
            formatted_return = return_obj.strftime("%Y-%m-%d")

            url = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights%20from%20{origin}%20to%20{destination}%20on%20{formatted_date}%20returning%20{formatted_return}"
                f"&hl=en&curr=GBP"
            )
        else:
            # One-way search
            url = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights%20to%20{destination}%20from%20{origin}%20on%20{formatted_date}"
                f"&hl=en&curr=GBP"
            )

        return url

    async def search_flights(self, origin: str, destination: str,
                           departure_date: str, adults: int = 1) -> List[Flight]:
        """
        Search for flights on Google Flights

        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Date in YYYY-MM-DD format
            adults: Number of adults

        Returns:
            List of Flight objects
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use 'async with' context manager")

        print(f"\nSearching Google Flights: {origin} -> {destination} on {departure_date}")

        # Build search URL
        url = self.build_search_url(origin, destination, departure_date, adults)
        print(f"URL: {url}")

        # Create new page
        page = await self.browser.new_page()

        try:
            # Navigate directly to search URL
            await page.goto(url, wait_until='networkidle', timeout=60000)

            print("Page loaded, checking for cookie consent...")
            await asyncio.sleep(3)

            # Handle cookie consent dialog
            try:
                # Try to find and click "Reject all" or "Accept all"
                reject_button = await page.query_selector('button:has-text("Reject all")')
                if reject_button:
                    print("Clicking 'Reject all' on cookie dialog")
                    await reject_button.click()
                    await asyncio.sleep(2)
                else:
                    # Try "Accept all" if "Reject all" not found
                    accept_button = await page.query_selector('button:has-text("Accept all")')
                    if accept_button:
                        print("Clicking 'Accept all' on cookie dialog")
                        await accept_button.click()
                        await asyncio.sleep(2)
            except Exception as e:
                print(f"No cookie dialog or error handling it: {e}")

            print("Waiting for page to stabilize and results to load...")
            await asyncio.sleep(15)  # Give Google Flights time to process the URL and load results

            # Try to extract flight data
            flights = await self.extract_flights(page, origin, destination, departure_date, url)

            print(f"Extracted {len(flights)} flights")

            # Delay before next request
            await asyncio.sleep(self.delay)

            return flights

        except Exception as e:
            print(f"Error searching flights: {e}")
            import traceback
            traceback.print_exc()
            return []

        finally:
            await page.close()

    async def extract_flights(self, page: Page, origin: str, destination: str, departure_date: str, url: str) -> List[Flight]:
        """
        Extract flight data from the Google Flights results page

        Args:
            page: Playwright page object with loaded results
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date
            url: Google Flights search URL

        Returns:
            List of Flight objects
        """
        flights = []

        try:
            # Google Flights uses specific selectors for flight cards
            # Strategy: Find all elements containing "round trip" text (price indicators)
            # Then get their parent containers which should be the flight cards

            # First try to find elements containing prices or flight times
            print("Searching for flight result containers...")
            all_divs = await page.query_selector_all('div')

            flight_cards = []
            for div in all_divs:
                text = await div.inner_text()
                # Check if this looks like a flight card (has price AND time pattern)
                has_price = '£' in text and any(char.isdigit() for char in text)
                has_time = ':' in text  # Flight times have colons
                has_airline_pattern = len(text) > 30 and len(text) < 500  # Flight cards have moderate text

                if has_price and has_time and has_airline_pattern:
                    # Check if it mentions typical flight info
                    if 'stop' in text.lower() or 'nonstop' in text.lower() or 'hr' in text.lower():
                        flight_cards.append(div)
                        if len(flight_cards) >= 50:  # Limit search
                            break

            print(f"Found {len(flight_cards)} potential flight cards")

            if not flight_cards:
                print("No flight cards found with known selectors")
                # Save HTML for debugging
                html = await page.content()
                with open("google_flights_no_results.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("Saved HTML to google_flights_no_results.html for debugging")
                return []

            print(f"Extracting data from {min(len(flight_cards), 20)} flight cards...")

            # Extract data from first 20 flight cards
            for i, card in enumerate(flight_cards[:20]):
                try:
                    # Get all text content
                    text = await card.inner_text()

                    # Debug: Print first 3 card texts to understand structure
                    if i < 3:
                        print(f"\n--- Card {i} text (first 200 chars) ---")
                        print(text[:200] if len(text) > 200 else text)
                        print("---")

                    # Parse the text to extract flight details
                    # Text format varies, but typically includes:
                    # - Times (e.g., "8:00 AM – 9:30 PM")
                    # - Duration (e.g., "13 hr 30 min")
                    # - Airline name
                    # - Stops (e.g., "1 stop", "Nonstop")
                    # - Price (e.g., "£456")

                    import re

                    # Extract price (look for £ symbol followed by numbers)
                    price_match = re.search(r'£\s*(\d+(?:,\d{3})*)', text)
                    price = float(price_match.group(1).replace(',', '')) if price_match else 0.0

                    # Extract times (look for time patterns like "8:00 AM" or "20:30")
                    time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)'
                    times = re.findall(time_pattern, text, re.IGNORECASE)
                    departure_time = times[0] if len(times) > 0 else "00:00"
                    arrival_time = times[1] if len(times) > 1 else "00:00"

                    # Extract duration (look for patterns like "13 hr 30 min" or "13h 30m")
                    duration_match = re.search(r'(\d+\s*hr?\s*\d*\s*m(?:in)?|\d+h\s*\d*m?)', text, re.IGNORECASE)
                    duration = duration_match.group(1) if duration_match else "0h"

                    # Extract stops
                    stops = 0
                    if 'nonstop' in text.lower() or 'direct' in text.lower():
                        stops = 0
                    elif '1 stop' in text.lower():
                        stops = 1
                    elif '2 stop' in text.lower():
                        stops = 2
                    elif 'stop' in text.lower():
                        # Try to find number before "stop"
                        stops_match = re.search(r'(\d+)\s*stop', text, re.IGNORECASE)
                        stops = int(stops_match.group(1)) if stops_match else 1

                    # Extract airline (first non-time, non-price capitalized word(s))
                    # This is a rough heuristic
                    lines = text.split('\n')
                    airline = "Unknown"
                    for line in lines:
                        line = line.strip()
                        if line and not re.search(r'\d{1,2}:\d{2}', line) and not '£' in line and not 'hr' in line.lower():
                            if len(line) > 2 and len(line) < 50:
                                airline = line
                                break

                    flight = Flight(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        price=price,
                        airline=airline,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        duration=duration,
                        stops=stops,
                        url=url
                    )

                    if price > 0:  # Only add flights with valid prices
                        flights.append(flight)

                except Exception as e:
                    print(f"Error extracting flight {i}: {e}")
                    continue

            # Deduplicate flights based on unique key (price + departure_time + airline)
            seen = set()
            unique_flights = []
            for flight in flights:
                # Create unique key
                key = (flight.price, flight.departure_time, flight.airline, flight.stops)
                if key not in seen:
                    seen.add(key)
                    unique_flights.append(flight)

            print(f"After deduplication: {len(unique_flights)} unique flights (was {len(flights)})")
            return unique_flights

        except Exception as e:
            print(f"Error in extract_flights: {e}")
            import traceback
            traceback.print_exc()

        return flights

    async def search_date_range(self, origin: str, destination: str,
                               start_date: str, end_date: str) -> List[Flight]:
        """
        Search flights across a date range

        Args:
            origin: Origin airport code
            destination: Destination airport code
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of all flights found across the date range
        """
        from datetime import datetime, timedelta

        all_flights = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            print(f"\nSearching date: {date_str}")
            flights = await self.search_flights(origin, destination, date_str)
            all_flights.extend(flights)
            current += timedelta(days=1)

        return all_flights

    async def search_multi_airport(self, origins: List[str], destinations: List[str],
                                  departure_date: str) -> List[Flight]:
        """
        Search flights from multiple origin airports to multiple destination airports

        Args:
            origins: List of origin airport codes (e.g., ['LHR', 'LGW', 'STN'])
            destinations: List of destination airport codes (e.g., ['HKG', 'MFM'])
            departure_date: Date in YYYY-MM-DD format

        Returns:
            List of all flights found across all airport combinations
        """
        all_flights = []

        for origin in origins:
            for destination in destinations:
                print(f"\nSearching: {origin} -> {destination}")
                flights = await self.search_flights(origin, destination, departure_date)
                all_flights.extend(flights)

        return all_flights

    async def search_roundtrip(self, origin: str, destination: str,
                              outbound_date: str, return_date: str,
                              adults: int = 1) -> List[RoundTripFlight]:
        """
        Search for round-trip flights on Google Flights

        Args:
            origin: Origin airport code
            destination: Destination airport code
            outbound_date: Outbound date in YYYY-MM-DD format
            return_date: Return date in YYYY-MM-DD format
            adults: Number of adults

        Returns:
            List of RoundTripFlight objects
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use 'async with' context manager")

        print(f"\nSearching Round Trip: {origin} ↔ {destination}")
        print(f"  Outbound: {outbound_date}, Return: {return_date}")

        # Build search URL with return date
        url = self.build_search_url(origin, destination, outbound_date, adults, return_date)
        print(f"URL: {url}")

        # Create new page
        page = await self.browser.new_page()

        try:
            # Navigate directly to search URL
            await page.goto(url, wait_until='networkidle', timeout=60000)

            print("Page loaded, checking for cookie consent...")
            await asyncio.sleep(3)

            # Handle cookie consent dialog
            try:
                reject_button = await page.query_selector('button:has-text("Reject all")')
                if reject_button:
                    print("Clicking 'Reject all' on cookie dialog")
                    await reject_button.click()
                    await asyncio.sleep(2)
                else:
                    accept_button = await page.query_selector('button:has-text("Accept all")')
                    if accept_button:
                        print("Clicking 'Accept all' on cookie dialog")
                        await accept_button.click()
                        await asyncio.sleep(2)
            except Exception as e:
                print(f"No cookie dialog or error handling it: {e}")

            print("Waiting for round-trip results to load...")
            await asyncio.sleep(15)  # Give Google Flights time to load round-trip results

            # Extract round-trip flights
            roundtrips = await self.extract_roundtrip_flights(page, origin, destination,
                                                             outbound_date, return_date, url)

            print(f"Extracted {len(roundtrips)} round-trip flights")

            # Delay before next request
            await asyncio.sleep(self.delay)

            return roundtrips

        except Exception as e:
            print(f"Error searching round-trip flights: {e}")
            import traceback
            traceback.print_exc()
            return []

        finally:
            await page.close()

    async def extract_roundtrip_flights(self, page: Page, origin: str, destination: str,
                                       outbound_date: str, return_date: str, url: str) -> List[RoundTripFlight]:
        """
        Extract round-trip flight data from Google Flights results page

        NOTE: Google Flights shows "starting from" prices for round-trips, not exact prices.
        We extract departure flight details and approximate prices for fuzzy comparison.

        Strategy:
        - Extract all visible flight cards with prices
        - Parse departure flight details (airline, times, duration, stops)
        - Use "starting from" price for ranking
        - Return top 3 by price and duration

        Args:
            page: Playwright page object with loaded results
            origin: Origin airport code
            destination: Destination airport code
            outbound_date: Outbound date
            return_date: Return date
            url: Google Flights search URL

        Returns:
            List of RoundTripFlight objects (prices are approximate "starting from" prices)
        """
        import re
        roundtrips = []

        try:
            print("Extracting round-trip flights (with approximate prices)...")
            await asyncio.sleep(3)  # Let page stabilize

            # Look for ALL divs containing flight-like data
            all_divs = await page.query_selector_all('div')
            print(f"Scanning {len(all_divs)} divs for flight data...")

            flight_candidates = []

            for div in all_divs:
                try:
                    text = await div.inner_text()

                    # Flight cards must have: price (£), time (:), and duration/stops
                    has_price = '£' in text
                    has_time = ':' in text and text.count(':') >= 2  # At least dep + arr time
                    has_flight_info = any(keyword in text.lower() for keyword in ['stop', 'nonstop', 'hr', 'min'])
                    reasonable_length = 50 < len(text) < 600

                    if has_price and has_time and has_flight_info and reasonable_length:
                        flight_candidates.append(text)

                        if len(flight_candidates) >= 20:  # Limit for performance
                            break

                except:
                    continue

            if not flight_candidates:
                print("❌ No flights found on page")
                return []

            # Parse each flight candidate
            for i, text in enumerate(flight_candidates[:15]):  # Limit to top 15
                try:
                    # Extract price (£ symbol followed by number)
                    price_match = re.search(r'£\s*(\d+(?:,\d{3})*)', text)
                    price = float(price_match.group(1).replace(',', '')) if price_match else 0.0

                    # Extract times
                    time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)'
                    times = re.findall(time_pattern, text, re.IGNORECASE)
                    dep_time = times[0] if len(times) > 0 else "00:00"
                    arr_time = times[1] if len(times) > 1 else "00:00"

                    # Extract duration
                    duration_match = re.search(r'(\d+\s*hr?\s*\d*\s*m(?:in)?|\d+h\s*\d*m?)', text, re.IGNORECASE)
                    duration = duration_match.group(1) if duration_match else "0h"

                    # Extract stops
                    stops = 0
                    if 'nonstop' in text.lower() or 'direct' in text.lower():
                        stops = 0
                    elif '1 stop' in text.lower():
                        stops = 1
                    elif '2 stop' in text.lower():
                        stops = 2
                    else:
                        stops_match = re.search(r'(\d+)\s*stop', text, re.IGNORECASE)
                        if stops_match:
                            stops = int(stops_match.group(1))

                    # Extract airline (first line that's not a time/price/duration)
                    lines = text.split('\n')
                    airline = "Unknown"
                    for line in lines:
                        line = line.strip()
                        if line and not re.search(r'\d{1,2}:\d{2}', line) and not '£' in line and not 'hr' in line.lower():
                            if 2 < len(line) < 50 and not line.lower() in ['select', 'remove', 'change']:
                                airline = line
                                break

                    # Only add if we have valid price and time
                    if price > 0 and dep_time != "00:00":
                        roundtrip = RoundTripFlight(
                            origin=origin,
                            destination=destination,
                            outbound_date=outbound_date,
                            return_date=return_date,
                            total_price=price,  # Approximate "starting from" price
                            outbound_airline=airline,
                            return_airline="Various",  # Unknown without clicking
                            outbound_departure_time=dep_time,
                            outbound_arrival_time=arr_time,
                            outbound_duration=duration,
                            outbound_stops=stops,
                            return_departure_time="",  # Unknown without clicking
                            return_arrival_time="",
                            return_duration="",
                            return_stops=0,
                            url=url
                        )
                        roundtrips.append(roundtrip)

                except Exception as e:
                    if i < 3:  # Only print errors for first few
                        print(f"  Error parsing flight {i}: {e}")
                    continue

            # Deduplicate based on price + departure time + airline
            seen = set()
            unique_roundtrips = []
            for rt in roundtrips:
                key = (rt.total_price, rt.outbound_departure_time, rt.outbound_airline)
                if key not in seen:
                    seen.add(key)
                    unique_roundtrips.append(rt)

            # Sort by price first, then by duration (shorter is better)
            def duration_to_minutes(duration_str):
                """Convert duration string like '13 hr 30 min' to total minutes"""
                try:
                    hours = re.search(r'(\d+)\s*hr?', duration_str, re.IGNORECASE)
                    mins = re.search(r'(\d+)\s*m(?:in)?', duration_str, re.IGNORECASE)
                    total = 0
                    if hours:
                        total += int(hours.group(1)) * 60
                    if mins:
                        total += int(mins.group(1))
                    return total
                except:
                    return 9999  # Large number for invalid durations

            unique_roundtrips.sort(key=lambda rt: (rt.total_price, duration_to_minutes(rt.outbound_duration)))

            # Return top 3
            top_3 = unique_roundtrips[:3]

            print(f"✓ Extracted {len(top_3)} best round-trip options (prices are approximate)")
            for i, rt in enumerate(top_3, 1):
                print(f"  {i}. £{rt.total_price:.0f} - {rt.outbound_airline} {rt.outbound_departure_time} ({rt.outbound_duration})")

            return top_3

        except Exception as e:
            print(f"Error in extract_roundtrip_flights: {e}")
            import traceback
            traceback.print_exc()

        return roundtrips


async def main():
    """Test the scraper"""
    print("=" * 80)
    print("Google Flights Scraper Test")
    print("=" * 80)

    async with GoogleFlightsScraper(headless=True, delay=2) as scraper:
        # Test 1: Single date search
        print("\n--- Test 1: Single date search ---")
        flights = await scraper.search_flights(
            origin="LHR",
            destination="HKG",
            departure_date="2026-02-05"
        )

        print(f"Found {len(flights)} flights for 2026-02-05:")
        for flight in flights:
            print(f"  {flight}")

        # Test 2: Multi-airport search (LHR to HK area: HKG, MFM, SZX)
        print("\n--- Test 2: Multi-airport search (LHR -> HK area) ---")
        london_airports = ["LHR"]
        hk_airports = ["HKG", "MFM", "SZX"]  # Hong Kong, Macau, Shenzhen

        multi_flights = await scraper.search_multi_airport(
            origins=london_airports,
            destinations=hk_airports,
            departure_date="2026-02-05"
        )

        print(f"\nTotal flights to {len(hk_airports)} HK area airports: {len(multi_flights)}")

        # Group by destination airport
        from collections import defaultdict
        by_dest = defaultdict(list)
        for flight in multi_flights:
            by_dest[flight.destination].append(flight)

        for airport in sorted(by_dest.keys()):
            if by_dest[airport]:  # Check if flights exist
                cheapest = min(f.price for f in by_dest[airport])
                print(f"  {airport}: {len(by_dest[airport])} flights (cheapest: £{cheapest})")
            else:
                print(f"  {airport}: No flights found")

        # Save results
        if multi_flights:
            with open("google_flights_test_results.json", "w") as f:
                json.dump([asdict(f) for f in multi_flights], f, indent=2)
            print("\nResults saved to google_flights_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
