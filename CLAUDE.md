# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flight search tool that finds optimal flight combinations for multi-segment trips (London ↔ Hong Kong/Taiwan ↔ London). The system scrapes flight data from Google Flights and applies constraint-based optimization to find the cheapest valid itineraries.

**Core Trip Pattern:**
1. London → Hong Kong area (5 airports × 3 HK airports)
2. Hong Kong area → Taiwan (3 HK airports × 2 Taiwan airports)
3. Taiwan → Hong Kong area (2 Taiwan airports × 3 HK airports)
4. Hong Kong area → London (3 HK airports × 5 London airports)

**Constraints:**
- Minimum 4 days in China (Hong Kong area)
- Minimum 10 days in Taiwan
- Chronological date ordering across all segments

## Architecture

### Core Components

**`GoogleFlightsScraper`** (google_flights_scraper.py)
- Web scraping engine using Playwright (async)
- Extracts flight data from Google Flights search results
- Supports both one-way (`search_flights`) and round-trip (`search_roundtrip`) searches
- Key methods:
  - `search_flights(origin, dest, date)` - Single one-way search
  - `search_date_range(origin, dest, start, end)` - Search across multiple dates
  - `search_multi_airport(origins, dests, date)` - Search all airport combinations
  - `search_roundtrip(origin, dest, outbound_date, return_date)` - Round-trip search
- Uses direct URL construction for reliability (not form filling)
- Implements deduplication and regex-based data extraction
- Handles cookie consent and rate limiting (configurable delay)

**`TripOptimizer`** (trip_finder.py & flight_search.py)
- Combinatorial optimization engine
- Validates date constraints and minimum stay requirements
- Uses `itertools.product` to generate all possible 4-segment combinations
- Sorts by total price to find cheapest options
- Method: `find_best_combinations(lon_to_hk, hk_to_lon, hk_to_tw, tw_to_hk, top_n)`

**Data Models**
- `Flight` - One-way flight (origin, dest, date, price, airline, times, duration, stops)
- `RoundTripFlight` - Round-trip flight with separate outbound/return details

### Integration Pattern

**trip_finder.py** is the primary end-to-end script that combines scraping + optimization:
1. Initialize scraper with `async with GoogleFlightsScraper() as scraper`
2. Scrape all 4 segments sequentially (using `search_date_range` for each airport pair)
3. Pass collected flights to `TripOptimizer.find_best_combinations()`
4. Output top N results and save to JSON

**Test Mode vs Full Search:**
- Test mode (default): Single airports, single dates per segment (~2 min runtime)
- Full mode: All airports, wide date ranges (significantly longer)
- Toggle via `test_mode` variable in trip_finder.py:97

### Legacy Components

**flight_search.py** - Original Amadeus API approach (deprecated)
- Requires `AMADEUS_API_KEY` and `AMADEUS_API_SECRET` environment variables
- Contains `FlightSearcher` and `TripOptimizer` classes
- Not actively used due to API rate limits and access restrictions

## Common Commands

### Setup
```bash
pip install -r requirements.txt
playwright install chromium  # Install browser for scraping
```

### Running Searches

**Full trip search (test mode - recommended for testing):**
```bash
python trip_finder.py
# Output: trip_results.json (top 10 combinations)
```

**Round-trip search:**
```bash
python trip_finder_roundtrip.py
# Output: trip_results_roundtrip.json
```

**Google Flights scraper (standalone test):**
```bash
python google_flights_scraper.py
# Runs built-in test suite with sample searches
```

**Skyscanner scraper (incomplete, not recommended):**
```bash
python skyscanner_scraper.py
# Note: Paused due to complex selectors
```

### Modifying Search Parameters

Edit trip_finder.py to change:
- **Airports:** london_airports, hk_airports, taiwan_airports (lines 101-103 for test mode, 112-114 for full)
- **Date ranges:** lon_hk_dates, hk_tw_dates, tw_hk_dates, hk_lon_dates (lines 106-109 or 117-120)
- **Constraints:** min_china_days, min_taiwan_days (line 93)
- **Mode:** test_mode = True/False (line 97)
- **Browser visibility:** headless=True/False (line 123)
- **Rate limiting:** delay=N seconds (line 123)

## Key Technical Details

### Web Scraping Strategy

**URL Construction (not form filling):**
- One-way: `google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{date}&hl=en&curr=GBP`
- Round-trip: Includes `returning%20{return_date}` in query
- This is more reliable than Playwright form interactions

**Data Extraction (google_flights_scraper.py:212-361):**
1. Find all `<div>` elements on page
2. Filter by content heuristics (has £, has :, has 'stop'/'hr', moderate length)
3. Extract via regex from text content:
   - Price: `£\s*(\d+(?:,\d{3})*)`
   - Times: `(\d{1,2}:\d{2}\s*(?:AM|PM)?)`
   - Duration: `(\d+\s*hr?\s*\d*\s*m(?:in)?)`
   - Stops: Text matching for "nonstop", "1 stop", etc.
   - Airline: First non-numeric line without £/hr/time
4. Deduplicate by (price, departure_time, airline, stops)

**Rate Limiting:**
- Default 2-3 second delay between requests
- 15-second wait for page stabilization after navigation
- Handles cookie consent dialogs automatically

### Date Validation Logic

(trip_finder.py:27-50 or flight_search.py:141-164)

```python
# Chronological order check
lon_to_hk < hk_to_tw < tw_to_hk < hk_to_lon

# Minimum stay checks
china_days = (hk_to_tw - lon_to_hk).days >= min_china_days
taiwan_days = (tw_to_hk - hk_to_tw).days >= min_taiwan_days
```

### Combinatorial Explosion

With full search parameters:
- 5 London airports × 3 HK airports × date_range1 = ~100-500 flights
- 3 HK airports × 2 Taiwan airports × date_range2 = ~50-200 flights
- 2 Taiwan airports × 3 HK airports × date_range3 = ~50-200 flights
- 3 HK airports × 5 London airports × date_range4 = ~100-500 flights

Total combinations: Product of above (~millions)
Valid combinations after constraint filtering: Typically hundreds

## Output Format

Results saved to `trip_results.json`:
```json
{
  "total_price": 1265.50,
  "total_days": 21,
  "china_days": 5,
  "taiwan_days": 11,
  "segments": {
    "london_to_hk": { "origin": "LHR", "destination": "HKG", ... },
    "hk_to_taiwan": { ... },
    "taiwan_to_hk": { ... },
    "hk_to_london": { ... }
  }
}
```

## Development Context

**Session History:** See `.claude/context.md` for detailed session logs including:
- Original Amadeus API approach and why it was abandoned
- Skyscanner scraper attempt and pivot to Google Flights
- Web scraping implementation details and debugging
- Integration of scraper with optimizer
- Test results and performance benchmarks

**Known Limitations:**
- Google Flights may change DOM structure (scraper uses content-based detection to be resilient)
- No API rate limit handling beyond delays (Google Flights doesn't expose rate limits)
- Test mode uses limited airports/dates for speed - full mode can take 30+ minutes
- Prices are scraped values and may not reflect booking fees/taxes
