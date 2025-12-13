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
                      seg3_date: str, seg4_date: str) -> bool:
        """Validate that dates meet minimum stay requirements"""

        date1 = datetime.strptime(seg1_date, "%Y-%m-%d")
        date2 = datetime.strptime(seg2_date, "%Y-%m-%d")
        date3 = datetime.strptime(seg3_date, "%Y-%m-%d")
        date4 = datetime.strptime(seg4_date, "%Y-%m-%d")

        # Check dates are in correct order
        if not (date1 < date2 < date3 < date4):
            return False

        # Check minimum stopover 1 stay (between segment 1 arrival and segment 2 departure)
        stopover1_days = (date2 - date1).days
        if stopover1_days < self.min_stopover1_days:
            return False

        # Check minimum stopover 2 stay (between segment 2 arrival and segment 3 departure)
        stopover2_days = (date3 - date2).days
        if stopover2_days < self.min_stopover2_days:
            return False

        return True

    def find_best_combinations(self, seg1: List[Flight], seg2: List[Flight],
                              seg3: List[Flight], seg4: List[Flight],
                              top_n: int = 10) -> List[Tuple[Flight, Flight, Flight, Flight, float]]:
        """Find the cheapest valid flight combinations"""

        valid_combos = []

        total_combinations = len(seg1) * len(seg2) * len(seg3) * len(seg4)
        print(f"\nAnalyzing {total_combinations:,} possible combinations...")
        print(f"  Segment 1: {len(seg1)} flights")
        print(f"  Segment 2: {len(seg2)} flights")
        print(f"  Segment 3: {len(seg3)} flights")
        print(f"  Segment 4: {len(seg4)} flights")

        for f1, f2, f3, f4 in product(seg1, seg2, seg3, seg4):
            # Check if dates are valid
            if self.validate_dates(f1.departure_date, f2.departure_date,
                                  f3.departure_date, f4.departure_date):
                total_price = f1.price + f2.price + f3.price + f4.price
                valid_combos.append((f1, f2, f3, f4, total_price))

        # Sort by total price
        valid_combos.sort(key=lambda x: x[4])

        print(f"✓ Found {len(valid_combos)} valid combinations meeting constraints")

        return valid_combos[:top_n]


@app.command()
def search(
    origins: str = typer.Option(..., "--origins", help="Comma-separated list of origin airport codes (e.g., LHR,LGW)"),
    stopover1: str = typer.Option(..., "--stopover1", help="Comma-separated list of first stopover airport codes (e.g., HKG,MFM)"),
    stopover2: str = typer.Option(..., "--stopover2", help="Comma-separated list of second stopover airport codes (e.g., TPE,KHH)"),
    seg1_dates: str = typer.Option("2026-02-05,2026-02-05", "--seg1-dates", help="Date range for segment 1 (origin->stopover1) as START,END"),
    seg2_dates: str = typer.Option("2026-02-10,2026-02-10", "--seg2-dates", help="Date range for segment 2 (stopover1->stopover2) as START,END"),
    seg3_dates: str = typer.Option("2026-02-21,2026-02-21", "--seg3-dates", help="Date range for segment 3 (stopover2->stopover1) as START,END"),
    seg4_dates: str = typer.Option("2026-02-26,2026-02-26", "--seg4-dates", help="Date range for segment 4 (stopover1->origin) as START,END"),
    min_stopover1_days: int = typer.Option(4, "--min-stopover1-days", help="Minimum days at first stopover"),
    min_stopover2_days: int = typer.Option(10, "--min-stopover2-days", help="Minimum days at second stopover"),
    top_n: int = typer.Option(10, "--top-n", help="Number of top results to return"),
    output: str = typer.Option("trip_results.json", "--output", help="Output JSON file"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    delay: int = typer.Option(2, "--delay", help="Delay between requests in seconds")
):
    """
    Find optimal multi-segment flight combinations.
    
    \b
    Examples:
      # London -> Hong Kong -> Taiwan -> Hong Kong -> London
      python trip_finder.py --origins LHR --stopover1 HKG --stopover2 TPE
      
      # Multiple airports
      python trip_finder.py --origins LHR,LGW --stopover1 HKG,MFM --stopover2 TPE,KHH
      
      # New York -> Dubai -> Singapore
      python trip_finder.py --origins JFK,EWR --stopover1 DXB --stopover2 SIN --min-stopover1-days 3
    """
    asyncio.run(run_search(
        origins, stopover1, stopover2,
        seg1_dates, seg2_dates, seg3_dates, seg4_dates,
        min_stopover1_days, min_stopover2_days,
        top_n, output, headless, delay
    ))


async def run_search(
    origins: str, stopover1: str, stopover2: str,
    seg1_dates: str, seg2_dates: str, seg3_dates: str, seg4_dates: str,
    min_stopover1_days: int, min_stopover2_days: int,
    top_n: int, output: str, headless: bool, delay: int
):
    """Async function to perform the search and optimization"""
    
    # Parse airports
    origins_list = [a.strip().upper() for a in origins.split(',')]
    stopover1_airports = [a.strip().upper() for a in stopover1.split(',')]
    stopover2_airports = [a.strip().upper() for a in stopover2.split(',')]

    # Parse date ranges
    seg1_start, seg1_end = seg1_dates.split(',')
    seg2_start, seg2_end = seg2_dates.split(',')
    seg3_start, seg3_end = seg3_dates.split(',')
    seg4_start, seg4_end = seg4_dates.split(',')

    print("=" * 80)
    print("FLIGHT TRIP FINDER: Multi-Segment Route Optimization")
    print("=" * 80)
    print(f"\nRoute:")
    print(f"  {','.join(origins_list)} → {','.join(stopover1_airports)} → {','.join(stopover2_airports)} → {','.join(stopover1_airports)} → {','.join(origins_list)}")
    print(f"\nConstraints:")
    print(f"  - Minimum {min_stopover1_days} days at stopover 1")
    print(f"  - Minimum {min_stopover2_days} days at stopover 2")
    print(f"\nDate Ranges:")
    print(f"  Segment 1: {seg1_start} to {seg1_end}")
    print(f"  Segment 2: {seg2_start} to {seg2_end}")
    print(f"  Segment 3: {seg3_start} to {seg3_end}")
    print(f"  Segment 4: {seg4_start} to {seg4_end}")
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

        # Segment 2: Stopover 1 -> Stopover 2
        print("\n" + "=" * 80)
        print("SEGMENT 2: Stopover 1 -> Stopover 2")
        print("=" * 80)
        seg2_flights = []
        for stopover1_airport in stopover1_airports:
            for stopover2_airport in stopover2_airports:
                print(f"\nSearching {stopover1_airport} -> {stopover2_airport} ({seg2_start} to {seg2_end})...")
                flights = await scraper.search_date_range(
                    stopover1_airport, stopover2_airport, seg2_start, seg2_end
                )
                seg2_flights.extend(flights)
                print(f"  Found {len(flights)} flights")
        print(f"\n✓ Total Segment 2 flights: {len(seg2_flights)}")

        # Segment 3: Stopover 2 -> Stopover 1
        print("\n" + "=" * 80)
        print("SEGMENT 3: Stopover 2 -> Stopover 1")
        print("=" * 80)
        seg3_flights = []
        for stopover2_airport in stopover2_airports:
            for stopover1_airport in stopover1_airports:
                print(f"\nSearching {stopover2_airport} -> {stopover1_airport} ({seg3_start} to {seg3_end})...")
                flights = await scraper.search_date_range(
                    stopover2_airport, stopover1_airport, seg3_start, seg3_end
                )
                seg3_flights.extend(flights)
                print(f"  Found {len(flights)} flights")
        print(f"\n✓ Total Segment 3 flights: {len(seg3_flights)}")

        # Segment 4: Stopover 1 -> Origin
        print("\n" + "=" * 80)
        print("SEGMENT 4: Stopover 1 -> Origin")
        print("=" * 80)
        seg4_flights = []
        for stopover1_airport in stopover1_airports:
            for origin in origins_list:
                print(f"\nSearching {stopover1_airport} -> {origin} ({seg4_start} to {seg4_end})...")
                flights = await scraper.search_date_range(
                    stopover1_airport, origin, seg4_start, seg4_end
                )
                seg4_flights.extend(flights)
                print(f"  Found {len(flights)} flights")
        print(f"\n✓ Total Segment 4 flights: {len(seg4_flights)}")

    # Find best combinations
    print("\n" + "=" * 80)
    print("FINDING OPTIMAL COMBINATIONS")
    print("=" * 80)

    if not all([seg1_flights, seg2_flights, seg3_flights, seg4_flights]):
        print("\n❌ ERROR: Not enough flights found in one or more segments")
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
