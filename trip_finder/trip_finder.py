#!/usr/bin/env python3
"""
Integrated Trip Finder
Combines Google Flights scraper with trip optimization to find best multi-segment trips
"""

import asyncio
import json
import typer
from datetime import datetime, timedelta
from itertools import product
from typing import List, Tuple, Optional
try:
    from .google_flights_scraper import GoogleFlightsScraper, Flight
except ImportError:
    from google_flights_scraper import GoogleFlightsScraper, Flight

app = typer.Typer(help="Find optimal multi-segment flight combinations")


class TripOptimizer:
    """Finds optimal flight combinations for multi-segment trips"""

    def __init__(self, min_stopover1_days: int = 4, min_stopover2_days: int = 10):
        self.min_stopover1_days = min_stopover1_days
        self.min_stopover2_days = min_stopover2_days

    def validate_dates(self, seg1_date: str, seg2_date: str,
                      seg3_date: Optional[str], seg4_date: Optional[str]) -> bool:
        """Validate that dates meet minimum stay requirements

        Single stopover (2 segments): origin→stopover1→origin
        - seg1: origin → stopover1
        - seg2: stopover1 → origin (return)
        - seg3: None, seg4: None

        Double stopover (3 segments): origin→stopover1→stopover2→origin
        - seg1: origin → stopover1
        - seg2: stopover1 → stopover2
        - seg3: stopover2 → origin (direct return)
        - seg4: None
        """

        date1 = datetime.strptime(seg1_date, "%Y-%m-%d")
        date2 = datetime.strptime(seg2_date, "%Y-%m-%d")

        # Single stopover case (2 segments)
        if seg3_date is None:
            # seg1: origin→stopover1, seg2: stopover1→origin
            if not (date1 < date2):
                return False

            stopover1_days = (date2 - date1).days
            if stopover1_days < self.min_stopover1_days:
                return False

            return True

        # Double stopover case (3 segments)
        date3 = datetime.strptime(seg3_date, "%Y-%m-%d")

        # Check dates are in correct order: seg1 < seg2 < seg3
        if not (date1 < date2 < date3):
            return False

        # Check minimum stopover 1 stay (between arrival at stopover1 and departure to stopover2)
        stopover1_days = (date2 - date1).days
        if stopover1_days < self.min_stopover1_days:
            return False

        # Check minimum stopover 2 stay (between arrival at stopover2 and return home)
        stopover2_days = (date3 - date2).days
        if stopover2_days < self.min_stopover2_days:
            return False

        return True

    def find_best_combinations(self, seg1: List[Flight], seg2: List[Flight],
                              seg3: List[Flight], seg4: List[Flight],
                              top_n: int = 10) -> List[Tuple[Flight, Flight, Optional[Flight], Optional[Flight], float]]:
        """Find the cheapest valid flight combinations

        Single stopover (2 segments): seg1, seg2, empty seg3, empty seg4
        Double stopover (3 segments): seg1, seg2, seg3, empty seg4
        """

        valid_combos = []

        # Single stopover case (2 segments)
        if not seg3:
            print(f"\nAnalyzing single stopover trips (2 segments)...")
            print(f"  Segment 1 (origin→stopover1): {len(seg1)} flights")
            print(f"  Segment 2 (stopover1→origin): {len(seg2)} flights")

            for f1, f2 in product(seg1, seg2):
                # Check if dates are valid
                if self.validate_dates(f1.departure_date, f2.departure_date, None, None):
                    total_price = f1.price + f2.price
                    valid_combos.append((f1, f2, None, None, total_price))

            # Sort by total price
            valid_combos.sort(key=lambda x: x[4])

            print(f"✓ Found {len(valid_combos)} valid single stopover trips")
            return valid_combos[:top_n]

        # Double stopover case (3 segments)
        total_combinations = len(seg1) * len(seg2) * len(seg3)
        print(f"\nAnalyzing double stopover trips (3 segments)...")
        print(f"  Segment 1 (origin→stopover1): {len(seg1)} flights")
        print(f"  Segment 2 (stopover1→stopover2): {len(seg2)} flights")
        print(f"  Segment 3 (stopover2→origin): {len(seg3)} flights")
        print(f"  Total combinations: {total_combinations:,}")

        for f1, f2, f3 in product(seg1, seg2, seg3):
            # Check if dates are valid
            if self.validate_dates(f1.departure_date, f2.departure_date,
                                  f3.departure_date, None):
                total_price = f1.price + f2.price + f3.price
                valid_combos.append((f1, f2, f3, None, total_price))

        # Sort by total price
        valid_combos.sort(key=lambda x: x[4])

        print(f"✓ Found {len(valid_combos)} valid double stopover trips")

        return valid_combos[:top_n]


@app.command()
def search(
    origins: str = typer.Option(..., "--origins", help="Comma-separated list of origin airport codes (e.g., LHR,LGW)"),
    stopover1: str = typer.Option(..., "--stopover1", help="Comma-separated list of first stopover airport codes (e.g., HKG,MFM)"),
    stopover2: Optional[str] = typer.Option(None, "--stopover2", help="Comma-separated list of second stopover airport codes (optional, e.g., TPE,KHH)"),
    seg1_dates: str = typer.Option("2026-02-05,2026-02-05", "--seg1-dates", help="Date range for segment 1 (origin->stopover1) as START,END"),
    seg2_dates: str = typer.Option("2026-02-10,2026-02-10", "--seg2-dates", help="Date range for segment 2 (stopover1->origin or stopover1->stopover2) as START,END"),
    seg3_dates: Optional[str] = typer.Option(None, "--seg3-dates", help="Date range for segment 3 (stopover2->stopover1) as START,END"),
    seg4_dates: Optional[str] = typer.Option(None, "--seg4-dates", help="Date range for segment 4 (stopover1->origin) as START,END"),
    min_stopover1_days: int = typer.Option(4, "--min-stopover1-days", help="Minimum days at first stopover"),
    min_stopover2_days: int = typer.Option(10, "--min-stopover2-days", help="Minimum days at second stopover"),
    top_n: int = typer.Option(10, "--top-n", help="Number of top results to return"),
    output: str = typer.Option("trip_results.json", "--output", help="Output JSON file"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    delay: int = typer.Option(2, "--delay", help="Delay between requests in seconds")
):
    """
    Find optimal multi-segment flight combinations.
    Supports single or double stopovers.

    \b
    Examples:
      # Single stopover (2 segments): London → Hong Kong → London
      python trip_finder.py --origins LHR --stopover1 HKG \\
        --seg1-dates 2026-02-05,2026-02-05 --seg2-dates 2026-02-15,2026-02-15

      # Double stopover (3 segments): London → Hong Kong → Taiwan → London
      python trip_finder.py --origins LHR --stopover1 HKG --stopover2 TPE \\
        --seg1-dates 2026-02-05,2026-02-05 --seg2-dates 2026-02-10,2026-02-10 \\
        --seg3-dates 2026-02-21,2026-02-21

      # Multiple airports with single stopover
      python trip_finder.py --origins LHR,LGW --stopover1 HKG,MFM \\
        --seg1-dates 2026-02-05,2026-02-07 --seg2-dates 2026-02-15,2026-02-17
    """
    asyncio.run(run_search(
        origins, stopover1, stopover2,
        seg1_dates, seg2_dates, seg3_dates, seg4_dates,
        min_stopover1_days, min_stopover2_days,
        top_n, output, headless, delay
    ))


async def run_search(
    origins: str, stopover1: str, stopover2: Optional[str],
    seg1_dates: str, seg2_dates: str, seg3_dates: Optional[str], seg4_dates: Optional[str],
    min_stopover1_days: int, min_stopover2_days: int,
    top_n: int, output: str, headless: bool, delay: int
):
    """Async function to perform the search and optimization"""

    # Parse airports
    origins_list = [a.strip().upper() for a in origins.split(',')]
    stopover1_airports = [a.strip().upper() for a in stopover1.split(',')]
    stopover2_airports = [a.strip().upper() for a in stopover2.split(',')] if stopover2 else []

    # Parse date ranges
    seg1_start, seg1_end = seg1_dates.split(',')
    seg2_start, seg2_end = seg2_dates.split(',')

    # For single stopover, seg3 and seg4 are not required
    if stopover2:
        if not seg3_dates or not seg4_dates:
            print("\n❌ ERROR: For double stopover, both --seg3-dates and --seg4-dates are required")
            return
        seg3_start, seg3_end = seg3_dates.split(',')
        seg4_start, seg4_end = seg4_dates.split(',')
    else:
        seg3_start = seg3_end = None
        seg4_start = seg4_end = None

    print("=" * 80)
    print("FLIGHT TRIP FINDER: Multi-Segment Route Optimization")
    print("=" * 80)
    print(f"\nRoute:")
    if stopover2:
        print(f"  {','.join(origins_list)} → {','.join(stopover1_airports)} → {','.join(stopover2_airports)} → {','.join(origins_list)}")
        print(f"  (3 segments: direct return from stopover2 to origin)")
    else:
        print(f"  {','.join(origins_list)} → {','.join(stopover1_airports)} → {','.join(origins_list)}")
        print(f"  (2 segments: simple round trip)")
    print(f"\nConstraints:")
    print(f"  - Minimum {min_stopover1_days} days at stopover 1")
    if stopover2:
        print(f"  - Minimum {min_stopover2_days} days at stopover 2")
    print(f"\nDate Ranges:")
    print(f"  Segment 1: {seg1_start} to {seg1_end}")
    print(f"  Segment 2: {seg2_start} to {seg2_end}")
    if stopover2:
        print(f"  Segment 3: {seg3_start} to {seg3_end}")
    print()

    # Initialize optimizer
    optimizer = TripOptimizer(
        min_stopover1_days=min_stopover1_days,
        min_stopover2_days=min_stopover2_days
    )

    # Create scraper
    async with GoogleFlightsScraper(headless=headless, delay=delay) as scraper:

        # Segment 1: Origin -> Stopover 1
        print("\n" + "=" * 80)
        print("SEGMENT 1: Origin -> Stopover 1")
        print("=" * 80)
        seg1_flights = []
        for origin in origins_list:
            for stopover1_airport in stopover1_airports:
                print(f"\nSearching {origin} -> {stopover1_airport} ({seg1_start} to {seg1_end})...")
                flights = await scraper.search_date_range(
                    origin, stopover1_airport, seg1_start, seg1_end
                )
                seg1_flights.extend(flights)
                print(f"  Found {len(flights)} flights")
        print(f"\n✓ Total Segment 1 flights: {len(seg1_flights)}")

        # Segment 2: Stopover1 -> Origin (single) or Stopover1 -> Stopover2 (double)
        print("\n" + "=" * 80)
        if stopover2:
            print("SEGMENT 2: Stopover 1 -> Stopover 2")
        else:
            print("SEGMENT 2: Stopover 1 -> Origin (Return)")
        print("=" * 80)
        seg2_flights = []
        if stopover2:
            # Double stopover: Stopover1 -> Stopover2
            for stopover1_airport in stopover1_airports:
                for stopover2_airport in stopover2_airports:
                    print(f"\nSearching {stopover1_airport} -> {stopover2_airport} ({seg2_start} to {seg2_end})...")
                    flights = await scraper.search_date_range(
                        stopover1_airport, stopover2_airport, seg2_start, seg2_end
                    )
                    seg2_flights.extend(flights)
                    print(f"  Found {len(flights)} flights")
        else:
            # Single stopover: Stopover1 -> Origin (return)
            for stopover1_airport in stopover1_airports:
                for origin in origins_list:
                    print(f"\nSearching {stopover1_airport} -> {origin} ({seg2_start} to {seg2_end})...")
                    flights = await scraper.search_date_range(
                        stopover1_airport, origin, seg2_start, seg2_end
                    )
                    seg2_flights.extend(flights)
                    print(f"  Found {len(flights)} flights")
        print(f"\n✓ Total Segment 2 flights: {len(seg2_flights)}")

        # Segment 3: Only for double stopover (Stopover2 -> Origin direct)
        seg3_flights = []
        seg4_flights = []  # Not used in new design
        if stopover2:
            # Segment 3: Stopover2 -> Origin (direct return)
            print("\n" + "=" * 80)
            print("SEGMENT 3: Stopover 2 -> Origin (Direct Return)")
            print("=" * 80)
            for stopover2_airport in stopover2_airports:
                for origin in origins_list:
                    print(f"\nSearching {stopover2_airport} -> {origin} ({seg3_start} to {seg3_end})...")
                    flights = await scraper.search_date_range(
                        stopover2_airport, origin, seg3_start, seg3_end
                    )
                    seg3_flights.extend(flights)
                    print(f"  Found {len(flights)} flights")
            print(f"\n✓ Total Segment 3 flights: {len(seg3_flights)}")

    # Find best combinations
    print("\n" + "=" * 80)
    print("FINDING OPTIMAL COMBINATIONS")
    print("=" * 80)

    # Check if we have flights
    if not seg1_flights or not seg2_flights:
        print("\n❌ ERROR: Not enough flights found in required segments (seg1, seg2)")
        print("   Cannot proceed with optimization")
        return

    if stopover2 and not seg3_flights:
        print("\n❌ ERROR: Not enough flights found for segment 3 (stopover2→origin)")
        print("   Cannot proceed with optimization")
        return

    best_combos = optimizer.find_best_combinations(
        seg1_flights, seg2_flights, seg3_flights, seg4_flights, top_n=top_n
    )

    # Display results
    if not best_combos:
        print("\n❌ No valid combinations found meeting all constraints")
        print("   Try expanding date ranges or relaxing constraints")
        return

    print("\n" + "=" * 80)
    print(f"TOP {len(best_combos)} CHEAPEST TRIP COMBINATIONS")
    print("=" * 80)

    for i, (f1, f2, f3, f4, total) in enumerate(best_combos, 1):
        print(f"\n{'='*80}")
        print(f"OPTION #{i} - TOTAL: £{total:.2f}")
        print(f"{'='*80}")

        # Calculate stays
        seg1_date = datetime.strptime(f1.departure_date, "%Y-%m-%d")
        seg2_date = datetime.strptime(f2.departure_date, "%Y-%m-%d")
        seg3_date = datetime.strptime(f3.departure_date, "%Y-%m-%d")
        seg4_date = datetime.strptime(f4.departure_date, "%Y-%m-%d")

        stopover1_days = (seg2_date - seg1_date).days
        stopover2_days = (seg3_date - seg2_date).days
        total_trip_days = (seg4_date - seg1_date).days

        print(f"\n1️⃣  SEGMENT 1: ORIGIN → STOPOVER 1")
        print(f"    {f1.origin} → {f1.destination}")
        print(f"    Date: {f1.departure_date}")
        print(f"    Airline: {f1.airline}")
        print(f"    Time: {f1.departure_time} → {f1.arrival_time}")
        print(f"    Duration: {f1.duration}, Stops: {f1.stops}")
        print(f"    Price: £{f1.price:.2f}")

        print(f"\n    📍 STAY AT STOPOVER 1: {stopover1_days} days")

        print(f"\n2️⃣  SEGMENT 2: STOPOVER 1 → STOPOVER 2")
        print(f"    {f2.origin} → {f2.destination}")
        print(f"    Date: {f2.departure_date}")
        print(f"    Airline: {f2.airline}")
        print(f"    Time: {f2.departure_time} → {f2.arrival_time}")
        print(f"    Duration: {f2.duration}, Stops: {f2.stops}")
        print(f"    Price: £{f2.price:.2f}")

        print(f"\n    📍 STAY AT STOPOVER 2: {stopover2_days} days")

        print(f"\n3️⃣  SEGMENT 3: STOPOVER 2 → STOPOVER 1")
        print(f"    {f3.origin} → {f3.destination}")
        print(f"    Date: {f3.departure_date}")
        print(f"    Airline: {f3.airline}")
        print(f"    Time: {f3.departure_time} → {f3.arrival_time}")
        print(f"    Duration: {f3.duration}, Stops: {f3.stops}")
        print(f"    Price: £{f3.price:.2f}")

        print(f"\n4️⃣  SEGMENT 4: STOPOVER 1 → ORIGIN")
        print(f"    {f4.origin} → {f4.destination}")
        print(f"    Date: {f4.departure_date}")
        print(f"    Airline: {f4.airline}")
        print(f"    Time: {f4.departure_time} → {f4.arrival_time}")
        print(f"    Duration: {f4.duration}, Stops: {f4.stops}")
        print(f"    Price: £{f4.price:.2f}")

        print(f"\n📊 TRIP SUMMARY:")
        print(f"    Total Duration: {total_trip_days} days")
        print(f"    Stopover 1 Stay: {stopover1_days} days")
        print(f"    Stopover 2 Stay: {stopover2_days} days")
        print(f"    Total Cost: £{total:.2f}")

    # Save results to JSON
    results = []
    for f1, f2, f3, f4, total in best_combos:
        # Calculate days
        seg1_date = datetime.strptime(f1.departure_date, "%Y-%m-%d")
        seg2_date = datetime.strptime(f2.departure_date, "%Y-%m-%d")
        seg3_date = datetime.strptime(f3.departure_date, "%Y-%m-%d")
        seg4_date = datetime.strptime(f4.departure_date, "%Y-%m-%d")

        results.append({
            "total_price": total,
            "total_days": (seg4_date - seg1_date).days,
            "stopover1_days": (seg2_date - seg1_date).days,
            "stopover2_days": (seg3_date - seg2_date).days,
            "segments": {
                "segment1_origin_to_stopover1": {
                    "origin": f1.origin,
                    "destination": f1.destination,
                    "date": f1.departure_date,
                    "airline": f1.airline,
                    "departure_time": f1.departure_time,
                    "arrival_time": f1.arrival_time,
                    "duration": f1.duration,
                    "stops": f1.stops,
                    "price": f1.price
                },
                "segment2_stopover1_to_stopover2": {
                    "origin": f2.origin,
                    "destination": f2.destination,
                    "date": f2.departure_date,
                    "airline": f2.airline,
                    "departure_time": f2.departure_time,
                    "arrival_time": f2.arrival_time,
                    "duration": f2.duration,
                    "stops": f2.stops,
                    "price": f2.price
                },
                "segment3_stopover2_to_stopover1": {
                    "origin": f3.origin,
                    "destination": f3.destination,
                    "date": f3.departure_date,
                    "airline": f3.airline,
                    "departure_time": f3.departure_time,
                    "arrival_time": f3.arrival_time,
                    "duration": f3.duration,
                    "stops": f3.stops,
                    "price": f3.price
                },
                "segment4_stopover1_to_origin": {
                    "origin": f4.origin,
                    "destination": f4.destination,
                    "date": f4.departure_date,
                    "airline": f4.airline,
                    "departure_time": f4.departure_time,
                    "arrival_time": f4.arrival_time,
                    "duration": f4.duration,
                    "stops": f4.stops,
                    "price": f4.price
                }
            }
        })

    with open(output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n\n{'='*80}")
    print(f"✓ Results saved to {output}")
    print("=" * 80)


if __name__ == "__main__":
    app()
