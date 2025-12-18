#!/usr/bin/env python3
"""
Round-Trip Based Trip Finder
Searches for 2 round trips instead of 4 one-way flights (often cheaper)
- Round trip 1: Origin ↔ Stopover 1
- Round trip 2: Stopover 1 ↔ Stopover 2
"""

import asyncio
import json
import typer
from datetime import datetime, timedelta
from itertools import product
from typing import List, Tuple, Optional
from dataclasses import asdict

app = typer.Typer(help="Find optimal round-trip flight combinations (often cheaper than one-ways)")
try:
    from .google_flights_scraper import GoogleFlightsScraper, RoundTripFlight
except ImportError:
    from google_flights_scraper import GoogleFlightsScraper, RoundTripFlight


def parse_date_range(date_string: str) -> List[str]:
    """
    Parse date string that can be:
    - Single date: "2026-02-05"
    - Comma-separated: "2026-02-05,2026-02-06,2026-02-07"
    - Range: "2026-02-05:2026-02-10" (inclusive)
    - Mix: "2026-02-05,2026-02-07:2026-02-09"

    Returns list of date strings in YYYY-MM-DD format
    """
    dates = []
    parts = [p.strip() for p in date_string.split(',')]

    for part in parts:
        if ':' in part:
            # Date range
            start_str, end_str = part.split(':')
            start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d")
            end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d")

            current = start_date
            while current <= end_date:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
        else:
            # Single date
            dates.append(part)

    return dates


class RoundTripOptimizer:
    """Finds optimal round-trip combinations for multi-segment trips"""

    def __init__(self, min_stopover1_days: int = 4, min_stopover2_days: int = 10):
        self.min_stopover1_days = min_stopover1_days
        self.min_stopover2_days = min_stopover2_days

    def validate_dates(self, rt1: RoundTripFlight, rt2: Optional[RoundTripFlight]) -> bool:
        """
        Validate that dates meet minimum stay requirements

        Args:
            rt1: Origin ↔ Stopover 1 round trip
            rt2: Stopover 1 ↔ Stopover 2 round trip (optional)

        Returns:
            True if dates are valid, False otherwise
        """
        # Parse dates for rt1
        rt1_outbound = datetime.strptime(rt1.outbound_date, "%Y-%m-%d")
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")

        if rt2 is None:
            # If no second round trip, validate only rt1
            return rt1_outbound < rt1_return

        # Parse dates for rt2
        rt2_outbound = datetime.strptime(rt2.outbound_date, "%Y-%m-%d")
        rt2_return = datetime.strptime(rt2.return_date, "%Y-%m-%d")

        # Check dates are in correct order:
        # 1. Depart origin to stopover 1 (rt1_outbound)
        # 2. Depart stopover 1 to stopover 2 (rt2_outbound)
        # 3. Return from stopover 2 to stopover 1 (rt2_return)
        # 4. Return from stopover 1 to origin (rt1_return)
        if not (rt1_outbound < rt2_outbound < rt2_return < rt1_return):
            return False

        # Check minimum stopover 1 stay
        stopover1_days = (rt2_outbound - rt1_outbound).days
        if stopover1_days < self.min_stopover1_days:
            return False

        # Check minimum stopover 2 stay
        stopover2_days = (rt2_return - rt2_outbound).days
        if stopover2_days < self.min_stopover2_days:
            return False

        return True

    def find_best_combinations(self, rt1_flights: List[RoundTripFlight],
                              rt2_flights: List[RoundTripFlight],
                              top_n: int = 10) -> List[Tuple[RoundTripFlight, RoundTripFlight, float]]:
        """
        Find the cheapest valid round-trip combinations

        Args:
            rt1_flights: Origin ↔ Stopover 1 round trips
            rt2_flights: Stopover 1 ↔ Stopover 2 round trips (empty list for single stopover)
            top_n: Number of top results to return

        Returns:
            List of tuples (rt1, rt2, total_price) where rt2 is None for single stopover
        """
        valid_combos = []

        # Handle single stopover case (no rt2)
        if not rt2_flights:
            print(f"\nAnalyzing single stopover trips...")
            print(f"  Round trip 1: {len(rt1_flights)} options")

            # For single stopover, just return sorted RT1 by price
            for rt1 in rt1_flights:
                valid_combos.append((rt1, None, rt1.total_price))

            # Sort by total price
            valid_combos.sort(key=lambda x: x[2])

            print(f"✓ Found {len(valid_combos)} valid single stopover trips")
            return valid_combos[:top_n]

        # Handle double stopover case (with rt2)
        total_combinations = len(rt1_flights) * len(rt2_flights)
        print(f"\nAnalyzing {total_combinations:,} possible combinations...")
        print(f"  Round trip 1: {len(rt1_flights)} options")
        print(f"  Round trip 2: {len(rt2_flights)} options")

        for rt1, rt2 in product(rt1_flights, rt2_flights):
            # Check if dates are valid
            if self.validate_dates(rt1, rt2):
                total_price = rt1.total_price + rt2.total_price
                valid_combos.append((rt1, rt2, total_price))

        # Sort by total price
        valid_combos.sort(key=lambda x: x[2])

        print(f"✓ Found {len(valid_combos)} valid combinations meeting constraints")

        return valid_combos[:top_n]



@app.command()
def search(
    origins: str = typer.Option(..., "--origins", help="Comma-separated list of origin airport codes"),
    stopover1: str = typer.Option(..., "--stopover1", help="Comma-separated list of first stopover airport codes"),
    stopover2: Optional[str] = typer.Option(None, "--stopover2", help="Comma-separated list of second stopover airport codes (optional)"),
    rt1_outbound: Optional[str] = typer.Option(None, "--rt1-outbound", help="Single outbound date for RT1 (YYYY-MM-DD)"),
    rt1_return: Optional[str] = typer.Option(None, "--rt1-return", help="Single return date for RT1 (YYYY-MM-DD)"),
    rt1_outbound_dates: Optional[str] = typer.Option(None, "--rt1-outbound-dates", help="Multiple outbound dates for RT1 (comma-separated)"),
    rt1_return_dates: Optional[str] = typer.Option(None, "--rt1-return-dates", help="Multiple return dates for RT1 (comma-separated)"),
    rt2_outbound: Optional[str] = typer.Option(None, "--rt2-outbound", help="Single outbound date for RT2 (YYYY-MM-DD)"),
    rt2_return: Optional[str] = typer.Option(None, "--rt2-return", help="Single return date for RT2 (YYYY-MM-DD)"),
    rt2_outbound_dates: Optional[str] = typer.Option(None, "--rt2-outbound-dates", help="Multiple outbound dates for RT2 (comma-separated)"),
    rt2_return_dates: Optional[str] = typer.Option(None, "--rt2-return-dates", help="Multiple return dates for RT2 (comma-separated)"),
    min_stopover1_days: int = typer.Option(4, "--min-stopover1-days", help="Minimum days at first stopover"),
    min_stopover2_days: int = typer.Option(10, "--min-stopover2-days", help="Minimum days at second stopover (ignored if stopover2 is not provided)"),
    top_n: int = typer.Option(10, "--top-n", help="Number of top results to return"),
    output: str = typer.Option("trip_results_roundtrip.json", "--output", help="Output JSON file"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    delay: int = typer.Option(2, "--delay", help="Delay between requests in seconds")
):
    """
    Find optimal round-trip flight combinations.
    Supports single or double stopovers.

    \b
    Examples:
      # Single stopover: London ↔ Hong Kong (one round trip)
      python trip_finder_roundtrip.py --origins LHR --stopover1 HKG \\
        --rt1-outbound 2026-02-05 --rt1-return 2026-02-15

      # Double stopover: London ↔ Hong Kong + Hong Kong ↔ Taiwan (two round trips)
      python trip_finder_roundtrip.py --origins LHR --stopover1 HKG --stopover2 TPE \\
        --rt1-outbound 2026-02-05 --rt1-return 2026-02-26 \\
        --rt2-outbound 2026-02-10 --rt2-return 2026-02-21

      # NYC ↔ Dubai (single stopover with multiple airports)
      python trip_finder_roundtrip.py --origins JFK,EWR --stopover1 DXB \\
        --rt1-outbound 2026-03-01 --rt1-return 2026-03-10
    """
    asyncio.run(run_search(
        origins, stopover1, stopover2,
        rt1_outbound, rt1_return, rt1_outbound_dates, rt1_return_dates,
        rt2_outbound, rt2_return, rt2_outbound_dates, rt2_return_dates,
        min_stopover1_days, min_stopover2_days,
        top_n, output, headless, delay
    ))


async def run_search(
    origins: str, stopover1: str, stopover2: Optional[str],
    rt1_outbound: Optional[str], rt1_return: Optional[str],
    rt1_outbound_dates: Optional[str], rt1_return_dates: Optional[str],
    rt2_outbound: Optional[str], rt2_return: Optional[str],
    rt2_outbound_dates: Optional[str], rt2_return_dates: Optional[str],
    min_stopover1_days: int, min_stopover2_days: int,
    top_n: int, output: str, headless: bool, delay: int
):
    """Async function to perform round-trip search and optimization"""
    
    # Parse airports
    origins_list = [a.strip().upper() for a in origins.split(',')]
    stopover1_airports = [a.strip().upper() for a in stopover1.split(',')]
    stopover2_airports = [a.strip().upper() for a in stopover2.split(',')] if stopover2 else []

    # Parse dates for RT1 (supports ranges like "2026-02-05:2026-02-10")
    if rt1_outbound:
        rt1_outbound_date_list = [rt1_outbound]
    elif rt1_outbound_dates:
        rt1_outbound_date_list = parse_date_range(rt1_outbound_dates)
    else:
        rt1_outbound_date_list = ["2026-02-05"]

    if rt1_return:
        rt1_return_date_list = [rt1_return]
    elif rt1_return_dates:
        rt1_return_date_list = parse_date_range(rt1_return_dates)
    else:
        rt1_return_date_list = ["2026-02-26"]

    # Parse dates for RT2 (if stopover2 is provided)
    if stopover2:
        if rt2_outbound:
            rt2_outbound_date_list = [rt2_outbound]
        elif rt2_outbound_dates:
            rt2_outbound_date_list = parse_date_range(rt2_outbound_dates)
        else:
            rt2_outbound_date_list = ["2026-02-10"]

        if rt2_return:
            rt2_return_date_list = [rt2_return]
        elif rt2_return_dates:
            rt2_return_date_list = parse_date_range(rt2_return_dates)
        else:
            rt2_return_date_list = ["2026-02-21"]

    print("=" * 80)
    print("ROUND-TRIP FLIGHT FINDER: Multi-Segment Route Optimization")
    print("=" * 80)
    print(f"\nRoute:")
    print(f"  Round Trip 1: {','.join(origins_list)} ↔ {','.join(stopover1_airports)}")
    if stopover2:
        print(f"  Round Trip 2: {','.join(stopover1_airports)} ↔ {','.join(stopover2_airports)}")
    print(f"\nConstraints:")
    print(f"  - Minimum {min_stopover1_days} days at stopover 1")
    if stopover2:
        print(f"  - Minimum {min_stopover2_days} days at stopover 2")
    print(f"\nSearch Strategy:")
    print(f"  - Searching round-trip fares (often cheaper than one-ways)")
    print()

    # Initialize optimizer
    optimizer = RoundTripOptimizer(
        min_stopover1_days=min_stopover1_days,
        min_stopover2_days=min_stopover2_days if stopover2 else 0
    )

    # Create scraper
    async with GoogleFlightsScraper(headless=headless, delay=delay) as scraper:

        # Round Trip 1: Origin ↔ Stopover 1
        print("\n" + "=" * 80)
        print("ROUND TRIP 1: Origin ↔ Stopover 1")
        print("=" * 80)
        rt1_roundtrips = []

        for origin in origins_list:
            for stopover1_airport in stopover1_airports:
                for outbound_date in rt1_outbound_date_list:
                    for return_date in rt1_return_date_list:
                        if return_date > outbound_date:
                            print(f"\nSearching {origin} ↔ {stopover1_airport}")
                            print(f"  Out: {outbound_date}, Return: {return_date}")
                            roundtrips = await scraper.search_roundtrip(
                                origin, stopover1_airport, outbound_date, return_date
                            )
                            rt1_roundtrips.extend(roundtrips)
                            print(f"  Found {len(roundtrips)} round-trip options")

        print(f"\n✓ Total Round Trip 1 options: {len(rt1_roundtrips)}")

        # Round Trip 2: Stopover 1 ↔ Stopover 2 (if stopover2 is provided)
        if stopover2:
            print("\n" + "=" * 80)
            print("ROUND TRIP 2: Stopover 1 ↔ Stopover 2")
            print("=" * 80)
            rt2_roundtrips = []

            for stopover1_airport in stopover1_airports:
                for stopover2_airport in stopover2_airports:
                    for outbound_date in rt2_outbound_date_list:
                        for return_date in rt2_return_date_list:
                            if return_date > outbound_date:
                                print(f"\nSearching {stopover1_airport} ↔ {stopover2_airport}")
                                print(f"  Out: {outbound_date}, Return: {return_date}")
                                roundtrips = await scraper.search_roundtrip(
                                    stopover1_airport, stopover2_airport, outbound_date, return_date
                                )
                                rt2_roundtrips.extend(roundtrips)
                                print(f"  Found {len(roundtrips)} round-trip options")

            print(f"\n✓ Total Round Trip 2 options: {len(rt2_roundtrips)}")

    # Find best combinations
    print("\n" + "=" * 80)
    print("FINDING OPTIMAL ROUND-TRIP COMBINATIONS")
    print("=" * 80)

    # Check if we have flights
    if not rt1_roundtrips:
        print("\n❌ ERROR: Not enough round-trip flights found for RT1")
        print("   Cannot proceed with optimization")
        return

    if stopover2 and not rt2_roundtrips:
        print("\n❌ ERROR: Not enough round-trip flights found for RT2")
        print("   Cannot proceed with optimization")
        return

    # Find best combinations (handles both single and double stopover)
    rt2_list = rt2_roundtrips if stopover2 else []
    best_combos = optimizer.find_best_combinations(
        rt1_roundtrips, rt2_list, top_n=top_n
    )

    # Display results
    if not best_combos:
        print("\n❌ No valid combinations found meeting all constraints")
        print("   Try expanding date ranges or relaxing constraints")
        return

    print("\n" + "=" * 80)
    print(f"TOP {len(best_combos)} CHEAPEST ROUND-TRIP COMBINATIONS")
    print("=" * 80)

    for i, (rt1, rt2, total) in enumerate(best_combos, 1):
        print(f"\n{'='*80}")
        print(f"OPTION #{i} - TOTAL: £{total:.2f}")
        print(f"{'='*80}")

        # Calculate stays
        rt1_outbound = datetime.strptime(rt1.outbound_date, "%Y-%m-%d")
        rt2_outbound = datetime.strptime(rt2.outbound_date, "%Y-%m-%d") if rt2 else None
        rt2_return = datetime.strptime(rt2.return_date, "%Y-%m-%d") if rt2 else None
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")

        stopover1_days = (rt2_outbound - rt1_outbound).days if rt2_outbound else 0
        stopover2_days = (rt2_return - rt2_outbound).days if rt2_outbound and rt2_return else 0
        total_trip_days = (rt1_return - rt1_outbound).days

        print(f"\n🔄 ROUND TRIP 1: ORIGIN ↔ STOPOVER 1 - £{rt1.total_price:.2f}")
        print(f"   Route: {rt1.origin} ↔ {rt1.destination}")
        print(f"\n   ✈️  OUTBOUND: {rt1.outbound_date}")
        print(f"      {rt1.outbound_airline}")
        print(f"      Time: {rt1.outbound_departure_time} → {rt1.outbound_arrival_time}")
        print(f"      Duration: {rt1.outbound_duration}, Stops: {rt1.outbound_stops}")
        print(f"\n   ✈️  RETURN: {rt1.return_date}")
        print(f"      {rt1.return_airline}")
        print(f"      Time: {rt1.return_departure_time} → {rt1.return_arrival_time}")
        print(f"      Duration: {rt1.return_duration}, Stops: {rt1.return_stops}")

        print(f"\n   📍 STAY AT STOPOVER 1: {stopover1_days} days")

        if rt2:
            print(f"\n🔄 ROUND TRIP 2: STOPOVER 1 ↔ STOPOVER 2 - £{rt2.total_price:.2f}")
            print(f"   Route: {rt2.origin} ↔ {rt2.destination}")
            print(f"\n   ✈️  OUTBOUND: {rt2.outbound_date}")
            print(f"      {rt2.outbound_airline}")
            print(f"      Time: {rt2.outbound_departure_time} → {rt2.outbound_arrival_time}")
            print(f"      Duration: {rt2.outbound_duration}, Stops: {rt2.outbound_stops}")
            print(f"\n   ✈️  RETURN: {rt2.return_date}")
            print(f"      {rt2.return_airline}")
            print(f"      Time: {rt2.return_departure_time} → {rt2.return_arrival_time}")
            print(f"      Duration: {rt2.return_duration}, Stops: {rt2.return_stops}")

            print(f"\n   📍 STAY AT STOPOVER 2: {stopover2_days} days")

        print(f"\n📊 TRIP SUMMARY:")
        print(f"    Total Duration: {total_trip_days} days")
        print(f"    Stopover 1 Stay: {stopover1_days} days")
        print(f"    Stopover 2 Stay: {stopover2_days} days" if stopover2_days > 0 else "")
        print(f"    Total Cost: £{total:.2f}")

    # Save results to JSON
    results = []
    for rt1, rt2, total in best_combos:
        rt1_outbound = datetime.strptime(rt1.outbound_date, "%Y-%m-%d")
        rt2_outbound = datetime.strptime(rt2.outbound_date, "%Y-%m-%d") if rt2 else None
        rt2_return = datetime.strptime(rt2.return_date, "%Y-%m-%d") if rt2 else None
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")

        result = {
            "total_price": total,
            "total_days": (rt1_return - rt1_outbound).days,
            "stopover1_days": (rt2_outbound - rt1_outbound).days if rt2_outbound else 0,
            "stopover2_days": (rt2_return - rt2_outbound).days if rt2_outbound and rt2_return else 0,
            "roundtrip1_origin_stopover1": asdict(rt1)
        }

        # Add roundtrip2 if it exists (double stopover)
        if rt2:
            result["roundtrip2_stopover1_stopover2"] = asdict(rt2)

        results.append(result)

    with open(output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n\n{'='*80}")
    print(f"✓ Results saved to {output}")
    print("=" * 80)


if __name__ == "__main__":
    app()
