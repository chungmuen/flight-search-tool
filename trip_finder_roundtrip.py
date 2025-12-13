#!/usr/bin/env python3
"""
Round-Trip Based Trip Finder
Searches for 2 round trips instead of 4 one-way flights (often cheaper)
- Round trip 1: Origin ↔ Stopover 1
- Round trip 2: Stopover 1 ↔ Stopover 2
"""

import asyncio
import json
import argparse
from datetime import datetime, timedelta
from itertools import product
from typing import List, Tuple
from google_flights_scraper import GoogleFlightsScraper, RoundTripFlight


class RoundTripOptimizer:
    """Finds optimal round-trip combinations for multi-segment trips"""

    def __init__(self, min_stopover1_days: int = 4, min_stopover2_days: int = 10):
        self.min_stopover1_days = min_stopover1_days
        self.min_stopover2_days = min_stopover2_days

    def validate_dates(self, rt1: RoundTripFlight, rt2: RoundTripFlight) -> bool:
        """
        Validate that dates meet minimum stay requirements

        Args:
            rt1: Origin ↔ Stopover 1 round trip
            rt2: Stopover 1 ↔ Stopover 2 round trip

        Returns:
            True if dates are valid, False otherwise
        """
        # Parse dates
        rt1_outbound = datetime.strptime(rt1.outbound_date, "%Y-%m-%d")
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")
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
            rt2_flights: Stopover 1 ↔ Stopover 2 round trips
            top_n: Number of top results to return

        Returns:
            List of tuples (rt1, rt2, total_price)
        """
        valid_combos = []

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


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Find optimal round-trip flight combinations (often cheaper than one-ways)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # London ↔ Hong Kong + Hong Kong ↔ Taiwan
  python trip_finder_roundtrip.py --origins LHR --stopover1 HKG --stopover2 TPE \\
    --rt1-outbound 2026-02-05 --rt1-return 2026-02-26 \\
    --rt2-outbound 2026-02-10 --rt2-return 2026-02-21

  # Multiple airports and dates
  python trip_finder_roundtrip.py --origins LHR,LGW --stopover1 HKG,MFM --stopover2 TPE,KHH \\
    --rt1-outbound-dates 2026-02-05,2026-02-06 --rt1-return-dates 2026-02-25,2026-02-26 \\
    --rt2-outbound-dates 2026-02-10,2026-02-11 --rt2-return-dates 2026-02-20,2026-02-21

  # NYC ↔ Dubai + Dubai ↔ Singapore
  python trip_finder_roundtrip.py --origins JFK --stopover1 DXB --stopover2 SIN \\
    --rt1-outbound 2026-03-01 --rt1-return 2026-03-17 \\
    --rt2-outbound 2026-03-05 --rt2-return 2026-03-13 \\
    --min-stopover1-days 3 --min-stopover2-days 7
        """)

    # Airport parameters
    parser.add_argument('--origins', type=str, required=True,
                       help='Comma-separated list of origin airport codes (e.g., LHR,LGW)')
    parser.add_argument('--stopover1', type=str, required=True,
                       help='Comma-separated list of first stopover airport codes (e.g., HKG,MFM)')
    parser.add_argument('--stopover2', type=str, required=True,
                       help='Comma-separated list of second stopover airport codes (e.g., TPE,KHH)')

    # Round trip 1 dates (Origin ↔ Stopover 1)
    parser.add_argument('--rt1-outbound', type=str,
                       help='Single outbound date for RT1 (YYYY-MM-DD). Use this OR --rt1-outbound-dates')
    parser.add_argument('--rt1-return', type=str,
                       help='Single return date for RT1 (YYYY-MM-DD). Use this OR --rt1-return-dates')
    parser.add_argument('--rt1-outbound-dates', type=str,
                       help='Multiple outbound dates for RT1 (comma-separated, e.g., 2026-02-05,2026-02-06)')
    parser.add_argument('--rt1-return-dates', type=str,
                       help='Multiple return dates for RT1 (comma-separated)')

    # Round trip 2 dates (Stopover 1 ↔ Stopover 2)
    parser.add_argument('--rt2-outbound', type=str,
                       help='Single outbound date for RT2 (YYYY-MM-DD). Use this OR --rt2-outbound-dates')
    parser.add_argument('--rt2-return', type=str,
                       help='Single return date for RT2 (YYYY-MM-DD). Use this OR --rt2-return-dates')
    parser.add_argument('--rt2-outbound-dates', type=str,
                       help='Multiple outbound dates for RT2 (comma-separated)')
    parser.add_argument('--rt2-return-dates', type=str,
                       help='Multiple return dates for RT2 (comma-separated)')

    # Constraint parameters
    parser.add_argument('--min-stopover1-days', type=int, default=4,
                       help='Minimum days at first stopover (default: 4)')
    parser.add_argument('--min-stopover2-days', type=int, default=10,
                       help='Minimum days at second stopover (default: 10)')

    # Output parameters
    parser.add_argument('--top-n', type=int, default=10,
                       help='Number of top results to return (default: 10)')
    parser.add_argument('--output', type=str, default='trip_results_roundtrip.json',
                       help='Output JSON file (default: trip_results_roundtrip.json)')

    # Scraper parameters
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browser in headless mode (default: True)')
    parser.add_argument('--delay', type=int, default=2,
                       help='Delay between requests in seconds (default: 2)')

    return parser.parse_args()


async def main():
    """Main execution - search round-trip flights and find optimal combinations"""

    # Parse arguments
    args = parse_args()

    # Parse airports
    origins = [a.strip().upper() for a in args.origins.split(',')]
    stopover1_airports = [a.strip().upper() for a in args.stopover1.split(',')]
    stopover2_airports = [a.strip().upper() for a in args.stopover2.split(',')]

    # Parse dates for RT1
    if args.rt1_outbound:
        rt1_outbound_dates = [args.rt1_outbound]
    elif args.rt1_outbound_dates:
        rt1_outbound_dates = [d.strip() for d in args.rt1_outbound_dates.split(',')]
    else:
        rt1_outbound_dates = ["2026-02-05"]  # Default

    if args.rt1_return:
        rt1_return_dates = [args.rt1_return]
    elif args.rt1_return_dates:
        rt1_return_dates = [d.strip() for d in args.rt1_return_dates.split(',')]
    else:
        rt1_return_dates = ["2026-02-26"]  # Default

    # Parse dates for RT2
    if args.rt2_outbound:
        rt2_outbound_dates = [args.rt2_outbound]
    elif args.rt2_outbound_dates:
        rt2_outbound_dates = [d.strip() for d in args.rt2_outbound_dates.split(',')]
    else:
        rt2_outbound_dates = ["2026-02-10"]  # Default

    if args.rt2_return:
        rt2_return_dates = [args.rt2_return]
    elif args.rt2_return_dates:
        rt2_return_dates = [d.strip() for d in args.rt2_return_dates.split(',')]
    else:
        rt2_return_dates = ["2026-02-21"]  # Default

    print("=" * 80)
    print("ROUND-TRIP FLIGHT FINDER: Multi-Segment Route Optimization")
    print("=" * 80)
    print(f"\nRoute:")
    print(f"  Round Trip 1: {','.join(origins)} ↔ {','.join(stopover1_airports)}")
    print(f"  Round Trip 2: {','.join(stopover1_airports)} ↔ {','.join(stopover2_airports)}")
    print(f"\nConstraints:")
    print(f"  - Minimum {args.min_stopover1_days} days at stopover 1")
    print(f"  - Minimum {args.min_stopover2_days} days at stopover 2")
    print(f"\nSearch Strategy:")
    print(f"  - Searching round-trip fares (often cheaper than one-ways)")
    print()

    # Initialize optimizer
    optimizer = RoundTripOptimizer(
        min_stopover1_days=args.min_stopover1_days,
        min_stopover2_days=args.min_stopover2_days
    )

    # Create scraper
    async with GoogleFlightsScraper(headless=args.headless, delay=args.delay) as scraper:

        # Round Trip 1: Origin ↔ Stopover 1
        print("\n" + "=" * 80)
        print("ROUND TRIP 1: Origin ↔ Stopover 1")
        print("=" * 80)
        rt1_roundtrips = []

        for origin in origins:
            for stopover1 in stopover1_airports:
                for outbound_date in rt1_outbound_dates:
                    for return_date in rt1_return_dates:
                        # Only search if return is after outbound
                        if return_date > outbound_date:
                            print(f"\nSearching {origin} ↔ {stopover1}")
                            print(f"  Out: {outbound_date}, Return: {return_date}")
                            roundtrips = await scraper.search_roundtrip(
                                origin, stopover1, outbound_date, return_date
                            )
                            rt1_roundtrips.extend(roundtrips)
                            print(f"  Found {len(roundtrips)} round-trip options")

        print(f"\n✓ Total Round Trip 1 options: {len(rt1_roundtrips)}")

        # Round Trip 2: Stopover 1 ↔ Stopover 2
        print("\n" + "=" * 80)
        print("ROUND TRIP 2: Stopover 1 ↔ Stopover 2")
        print("=" * 80)
        rt2_roundtrips = []

        for stopover1 in stopover1_airports:
            for stopover2 in stopover2_airports:
                for outbound_date in rt2_outbound_dates:
                    for return_date in rt2_return_dates:
                        # Only search if return is after outbound
                        if return_date > outbound_date:
                            print(f"\nSearching {stopover1} ↔ {stopover2}")
                            print(f"  Out: {outbound_date}, Return: {return_date}")
                            roundtrips = await scraper.search_roundtrip(
                                stopover1, stopover2, outbound_date, return_date
                            )
                            rt2_roundtrips.extend(roundtrips)
                            print(f"  Found {len(roundtrips)} round-trip options")

        print(f"\n✓ Total Round Trip 2 options: {len(rt2_roundtrips)}")

    # Find best combinations
    print("\n" + "=" * 80)
    print("FINDING OPTIMAL ROUND-TRIP COMBINATIONS")
    print("=" * 80)

    if not all([rt1_roundtrips, rt2_roundtrips]):
        print("\n❌ ERROR: Not enough round-trip flights found")
        print("   Cannot proceed with optimization")
        return

    best_combos = optimizer.find_best_combinations(
        rt1_roundtrips, rt2_roundtrips, top_n=args.top_n
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
        rt2_outbound = datetime.strptime(rt2.outbound_date, "%Y-%m-%d")
        rt2_return = datetime.strptime(rt2.return_date, "%Y-%m-%d")
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")

        stopover1_days = (rt2_outbound - rt1_outbound).days
        stopover2_days = (rt2_return - rt2_outbound).days
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
        print(f"    Stopover 2 Stay: {stopover2_days} days")
        print(f"    Total Cost: £{total:.2f}")

    # Save results to JSON
    results = []
    for rt1, rt2, total in best_combos:
        rt1_outbound = datetime.strptime(rt1.outbound_date, "%Y-%m-%d")
        rt2_outbound = datetime.strptime(rt2.outbound_date, "%Y-%m-%d")
        rt2_return = datetime.strptime(rt2.return_date, "%Y-%m-%d")
        rt1_return = datetime.strptime(rt1.return_date, "%Y-%m-%d")

        results.append({
            "total_price": total,
            "total_days": (rt1_return - rt1_outbound).days,
            "stopover1_days": (rt2_outbound - rt1_outbound).days,
            "stopover2_days": (rt2_return - rt2_outbound).days,
            "roundtrip1_origin_stopover1": {
                "origin": rt1.origin,
                "destination": rt1.destination,
                "outbound_date": rt1.outbound_date,
                "return_date": rt1.return_date,
                "total_price": rt1.total_price,
                "outbound": {
                    "airline": rt1.outbound_airline,
                    "departure_time": rt1.outbound_departure_time,
                    "arrival_time": rt1.outbound_arrival_time,
                    "duration": rt1.outbound_duration,
                    "stops": rt1.outbound_stops
                },
                "return": {
                    "airline": rt1.return_airline,
                    "departure_time": rt1.return_departure_time,
                    "arrival_time": rt1.return_arrival_time,
                    "duration": rt1.return_duration,
                    "stops": rt1.return_stops
                }
            },
            "roundtrip2_stopover1_stopover2": {
                "origin": rt2.origin,
                "destination": rt2.destination,
                "outbound_date": rt2.outbound_date,
                "return_date": rt2.return_date,
                "total_price": rt2.total_price,
                "outbound": {
                    "airline": rt2.outbound_airline,
                    "departure_time": rt2.outbound_departure_time,
                    "arrival_time": rt2.outbound_arrival_time,
                    "duration": rt2.outbound_duration,
                    "stops": rt2.outbound_stops
                },
                "return": {
                    "airline": rt2.return_airline,
                    "departure_time": rt2.return_departure_time,
                    "arrival_time": rt2.return_arrival_time,
                    "duration": rt2.return_duration,
                    "stops": rt2.return_stops
                }
            }
        })

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n\n{'='*80}")
    print(f"✓ Results saved to {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
