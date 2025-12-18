![CI](https://github.com/chungmuen/flight-search-tool/actions/workflows/ci.yml/badge.svg)

# Flight Search Tool

Automated tool to find the cheapest multi-segment flight combinations with single or double stopovers. Supports **any route** with flexible segment patterns:
- **Single stopover** (2 segments): e.g., London → Hong Kong → London
- **Double stopover** (3 segments): e.g., London → Hong Kong → Taiwan → London (direct return)

## Features

- **Modern CLI with Typer**:
  - Rich, user-friendly command-line interface
  - Automatic help generation with formatted output
  - Type-safe parameter validation
  - Shell completion support (bash, zsh, fish, PowerShell)
  - Clear error messages and input validation
- **Flexible Multi-Segment Search**:
  - Configure any origin, stopover 1, and stopover 2 locations via command-line
  - Search multiple airports per location (e.g., all London airports, all NYC airports)
  - Set custom date ranges for each flight segment
  - Define minimum stay requirements at each stopover
  - Finds and ranks the cheapest valid combinations
- **Web Scraping**:
  - Scrapes real-time flight data from Google Flights using Playwright
  - Extracts flight details: price, times, airlines, stops, duration
  - Handles dynamic content and cookie consent dialogs
  - Supports multi-airport and date range searches
  - Automatic deduplication of results
- **Trip Optimization**:
  - Combinatorial analysis of all possible flight combinations
  - Validates chronological date ordering and minimum stay constraints
  - Outputs top N cheapest options
  - Saves results to JSON for further analysis

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browser

```bash
playwright install chromium
```

This downloads the Chromium browser needed for web scraping.

### 3. (Optional) Enable Shell Completion

Typer provides automatic shell completion. To install it:

```bash
# For bash
python trip_finder.py --install-completion bash

# For zsh
python trip_finder.py --install-completion zsh

# For fish
python trip_finder.py --install-completion fish

# For PowerShell
python trip_finder.py --install-completion powershell
```

After installation, restart your shell to enable tab completion for all parameters.

## Usage

### Multi-Segment Trip Finder (Primary Tool)

The trip finder supports **any** multi-segment route with single or double stopovers. You specify the airports and constraints via command-line arguments.

**Single stopover (2 segments: London → Hong Kong → London):**

```bash
python trip_finder.py --origins LHR --stopover1 HKG \
  --seg1-dates 2026-02-05,2026-02-05 \
  --seg2-dates 2026-02-15,2026-02-15
```

**Double stopover (3 segments: London → Hong Kong → Taiwan → London):**

```bash
python trip_finder.py --origins LHR --stopover1 HKG --stopover2 TPE
```

Note: With double stopover, you return directly from the second stopover to origin (not back through the first stopover).

**Multiple airports per location:**

```bash
python trip_finder.py \
  --origins LHR,LGW,STN \
  --stopover1 HKG,MFM,SZX \
  --stopover2 TPE,KHH \
  --min-stopover1-days 4 \
  --min-stopover2-days 10
```

**Custom dates and constraints (double stopover - 3 segments):**

```bash
python trip_finder.py \
  --origins LHR \
  --stopover1 HKG \
  --stopover2 TPE \
  --seg1-dates 2026-02-05,2026-02-07 \
  --seg2-dates 2026-02-10,2026-02-12 \
  --seg3-dates 2026-02-21,2026-02-23 \
  --min-stopover1-days 5 \
  --min-stopover2-days 10 \
  --top-n 5 \
  --output my_results.json
```

**Different route (NYC → Dubai → Singapore → NYC - direct return):**

```bash
python trip_finder.py \
  --origins JFK,EWR \
  --stopover1 DXB \
  --stopover2 SIN \
  --min-stopover1-days 3 \
  --min-stopover2-days 7 \
  --seg1-dates 2026-03-01,2026-03-01 \
  --seg2-dates 2026-03-05,2026-03-05 \
  --seg3-dates 2026-03-13,2026-03-13
```

**Available parameters:**

For a complete list of parameters with descriptions, run:

```bash
python trip_finder.py --help
```

Key parameters:
- `--origins` - Origin airport codes (comma-separated) **[required]**
- `--stopover1` - First stopover airport codes (comma-separated) **[required]**
- `--stopover2` - Second stopover airport codes (optional for single stopover)
- `--seg1-dates` - Date range for origin→stopover1 (START,END format)
- `--seg2-dates` - Date range for stopover1→origin (single) or stopover1→stopover2 (double)
- `--seg3-dates` - Date range for stopover2→origin (double stopover only, direct return)
- `--min-stopover1-days` - Minimum days at first stopover (default: 4)
- `--min-stopover2-days` - Minimum days at second stopover (default: 10)
- `--top-n` - Number of results to return (default: 10)
- `--output` - Output JSON filename (default: trip_results.json)
- `--delay` - Delay between requests in seconds (default: 2)
- `--headless` / `--no-headless` - Run browser in headless mode (default: headless)

**Segment Patterns:**
- **Single stopover**: 2 segments (origin→stopover1→origin)
- **Double stopover**: 3 segments (origin→stopover1→stopover2→origin, direct return)

### Google Flights Scraper (Standalone)

Test the scraper independently:

```bash
python google_flights_scraper.py
```

This runs built-in tests to verify scraping functionality.

### Round-Trip Finder

Searches for 2 round-trip tickets instead of 4 one-way flights (often finds cheaper prices).

**⚠️ Important Note About Prices:**
Round-trip prices are **approximate "starting from" prices** shown on Google Flights initial page. For exact final prices and return flight details, click the Google Flights URL included in the results.

**Basic usage:**

```bash
python trip_finder_roundtrip.py \
  --origins LHR \
  --stopover1 HKG \
  --stopover2 TPE \
  --rt1-outbound 2026-02-05 \
  --rt1-return 2026-02-26 \
  --rt2-outbound 2026-02-10 \
  --rt2-return 2026-02-21
```

**With custom minimum stay requirements:**

```bash
python trip_finder_roundtrip.py \
  --origins JFK \
  --stopover1 DXB \
  --stopover2 SIN \
  --rt1-outbound 2026-03-01 \
  --rt1-return 2026-03-17 \
  --rt2-outbound 2026-03-05 \
  --rt2-return 2026-03-13 \
  --min-stopover1-days 3 \
  --min-stopover2-days 7
```

**Multiple airports and dates:**

```bash
python trip_finder_roundtrip.py \
  --origins LHR,LGW \
  --stopover1 HKG,MFM \
  --stopover2 TPE,KHH \
  --rt1-outbound-dates 2026-02-05,2026-02-06 \
  --rt1-return-dates 2026-02-25,2026-02-26 \
  --rt2-outbound-dates 2026-02-10,2026-02-11 \
  --rt2-return-dates 2026-02-20,2026-02-21 \
  --min-stopover1-days 5 \
  --min-stopover2-days 12
```

**How it works:**
- Round Trip 1: Origin ↔ Stopover 1 (e.g., London ↔ Hong Kong)
- Round Trip 2: Stopover 1 ↔ Stopover 2 (e.g., Hong Kong ↔ Taiwan)
- Often cheaper than booking 4 separate one-way flights
- Validates minimum stay requirements at each stopover (default: 4 days at stopover 1, 10 days at stopover 2)

**What you get:**
- **Outbound flights**: Full details (airline, times, duration, stops)
- **Return flights**: Marked as "Various" (details available via Google Flights URL)
- **Prices**: Approximate "starting from" prices for ranking and comparison
- **Google Flights URL**: Click to see exact return options and final prices
- **Top 3 options** per search, sorted by price and duration

**Available parameters:**

Run `python trip_finder_roundtrip.py --help` for complete documentation. Key parameters:
- `--origins`, `--stopover1`, `--stopover2` - Airport codes **[required]**
- `--rt1-outbound`, `--rt1-return` - Single dates for RT1
- `--rt2-outbound`, `--rt2-return` - Single dates for RT2
- `--rt1-outbound-dates`, `--rt1-return-dates` - Multiple dates for RT1 (comma-separated)
- `--rt2-outbound-dates`, `--rt2-return-dates` - Multiple dates for RT2 (comma-separated)
- `--min-stopover1-days`, `--min-stopover2-days` - Minimum stay requirements
- `--headless` / `--no-headless` - Browser display mode

## Development History

### Initial Approach: Amadeus API
- The project initially relied on the Amadeus API for flight data.
- Limitations:
  - API rate limits and access restrictions.
  - Limited real-time data availability.
- Pivoted to web scraping for more flexibility and real-time data.

### Web Scraping Development
- **Google Flights Scraper**:
  - Fully functional scraper using Playwright.
  - Extracts flight details (price, times, airlines, stops) for multi-airport and date range searches.
  - Handles dynamic content and cookie consent dialogs.
  - **One-way searches**: Full accuracy with exact prices.
  - **Round-trip searches**: Extracts approximate "starting from" prices and outbound flight details. Google Flights URL provided for exact pricing.
- **Skyscanner Scraper**:
  - Initial attempt made but paused due to Skyscanner's complex structure.

### Trip Optimizer Integration
- Combined Google Flights scraping with trip optimization logic.
- Supports fully parameterized multi-segment searches for any route.
- Two search modes:
  - **One-way finder**: Flexible 2-3 segment trips
    - Single stopover: 2 segments (origin→stopover1→origin)
    - Double stopover: 3 segments (origin→stopover1→stopover2→origin, direct return)
  - **Round-trip finder**: 1-2 round trips (often cheaper)
    - Single stopover: 1 round trip (origin↔stopover1)
    - Double stopover: 2 round trips (origin↔stopover1 + stopover1↔stopover2)
- Validates constraints:
  - Customizable minimum stay requirements at each stopover.
  - Chronological date validation.
- Outputs top N cheapest valid combinations to JSON.

### Modern CLI with Typer
- Migrated from argparse to Typer for improved user experience.
- Features:
  - Rich formatted help output with tables and colors.
  - Type-safe parameter validation.
  - Shell completion support for all major shells.
  - Boolean flags with `--flag/--no-flag` syntax.
  - Automatic required parameter enforcement.
- Comprehensive unit tests (28 tests) covering scrapers and optimizers.

## Example Output

```
#1 - Total: £987.50
--------------------------------------------------------------------------------
  London -> HK:  LHR -> HKG | 2026-02-05 | BA031 | £445.00
  [Stay in China: 5 days]
  HK -> Taiwan:  HKG -> TPE | 2026-02-10 | CX420 | £89.00
  [Stay in Taiwan: 10 days]
  Taiwan -> HK:  TPE -> HKG | 2026-02-20 | CX421 | £92.50
  HK -> London:  HKG -> LHR | 2026-02-21 | BA032 | £361.00
```

## Notes

- Searches can take several minutes depending on the number of airports and date ranges.
- **One-way finder**: Results are scraped from Google Flights and reflect real-time prices.
- **Round-trip finder**: Prices are approximate "starting from" prices. Click the Google Flights URL in results for exact final prices.
- Use `--delay` parameter to adjust wait time between requests (default: 2 seconds).
- Headless mode is enabled by default; use `--no-headless` to see the browser.
- All times and prices are as displayed on Google Flights at the time of search.

## Testing

The project includes comprehensive unit tests:

```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test files
python -m unittest tests.test_google_flights_scraper
python -m unittest tests.test_trip_optimizer
python -m unittest tests.test_roundtrip_optimizer
```

## Troubleshooting

**No results found**
- Verify airport codes are correct (use IATA codes like LHR, JFK, HKG).
- Check that dates are in the future.
- Try wider date ranges.
- Ensure there are actual flights on those routes.

**Browser/Playwright errors**
- Make sure Playwright browsers are installed: `playwright install chromium`
- Try running with `--no-headless` to see what's happening.
- Check your internet connection.

**Scraping errors**
- Google Flights may have updated their layout; the scraper may need updates.
- Try increasing `--delay` to give pages more time to load.
- Check if you're being rate-limited (try longer delays).