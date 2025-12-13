![CI](https://github.com/chungmuen/flight-search-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/chungmuen/flight-search-tool/actions/workflows/ci.yml)

# Flight Search Tool

Automated tool to find the cheapest multi-segment flight combinations with two stopovers. Supports **any route** (e.g., London → Hong Kong → Taiwan → London, NYC → Dubai → Singapore → NYC, etc.).

## Features

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

## Usage

### Multi-Segment Trip Finder (Primary Tool)

The trip finder supports **any** multi-segment route with two stopovers. You specify the airports and constraints via command-line arguments.

**Basic usage (London → Hong Kong → Taiwan → Hong Kong → London):**

```bash
python trip_finder.py --origins LHR --stopover1 HKG --stopover2 TPE
```

**Multiple airports per location:**

```bash
python trip_finder.py \
  --origins LHR,LGW,STN \
  --stopover1 HKG,MFM,SZX \
  --stopover2 TPE,KHH \
  --min-stopover1-days 4 \
  --min-stopover2-days 10
```

**Custom dates and constraints:**

```bash
python trip_finder.py \
  --origins LHR \
  --stopover1 HKG \
  --stopover2 TPE \
  --seg1-dates 2026-02-05,2026-02-07 \
  --seg2-dates 2026-02-10,2026-02-12 \
  --seg3-dates 2026-02-21,2026-02-23 \
  --seg4-dates 2026-02-26,2026-02-28 \
  --min-stopover1-days 5 \
  --min-stopover2-days 10 \
  --top-n 5 \
  --output my_results.json
```

**Different route (New York → Dubai → Singapore → Dubai → New York):**

```bash
python trip_finder.py \
  --origins JFK,EWR \
  --stopover1 DXB \
  --stopover2 SIN \
  --min-stopover1-days 3 \
  --min-stopover2-days 7 \
  --seg1-dates 2026-03-01,2026-03-01 \
  --seg2-dates 2026-03-05,2026-03-05 \
  --seg3-dates 2026-03-13,2026-03-13 \
  --seg4-dates 2026-03-17,2026-03-17
```

**Available parameters:**

```bash
python trip_finder.py --help
```

- `--origins` - Origin airport codes (comma-separated)
- `--stopover1` - First stopover airport codes (comma-separated)
- `--stopover2` - Second stopover airport codes (comma-separated)
- `--seg1-dates` - Date range for origin→stopover1 (START,END format)
- `--seg2-dates` - Date range for stopover1→stopover2
- `--seg3-dates` - Date range for stopover2→stopover1
- `--seg4-dates` - Date range for stopover1→origin
- `--min-stopover1-days` - Minimum days at first stopover (default: 4)
- `--min-stopover2-days` - Minimum days at second stopover (default: 10)
- `--top-n` - Number of results to return (default: 10)
- `--output` - Output JSON filename (default: trip_results.json)
- `--delay` - Delay between requests in seconds (default: 2)
- `--headless` - Run browser in headless mode

### Google Flights Scraper (Standalone)

Test the scraper independently:

```bash
python google_flights_scraper.py
```

This runs built-in tests to verify scraping functionality.

### Round-Trip Finder

Searches for 2 round-trip tickets instead of 4 one-way flights (often finds cheaper prices).

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
- **Skyscanner Scraper**:
  - Initial attempt made but paused due to Skyscanner's complex structure.

### Trip Optimizer Integration
- Combined Google Flights scraping with trip optimization logic.
- Supports multi-segment searches:
  - London → Hong Kong area
  - Hong Kong area → Taiwan
  - Taiwan → Hong Kong area
  - Hong Kong area → London
- Validates constraints:
  - Minimum 4 days in China.
  - Minimum 10 days in Taiwan.
- Outputs top 10 cheapest valid combinations to `trip_results.json`.

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

- The free Amadeus API tier has rate limits (check their documentation).
- Searches can take several minutes depending on date ranges.
- Results are from the test API environment (may not reflect real prices).
- For production use, switch to production API credentials.
- Consider adding delays between API calls to avoid rate limiting.

## Troubleshooting

**Error: "Please set AMADEUS_API_KEY..."**
- Make sure environment variables are set correctly.
- Restart your terminal after setting variables.

**Error: "401 Unauthorized"**
- Verify your API credentials are correct.
- Check if your API key has expired.

**No results found**
- Try wider date ranges.
- Check if airport codes are correct.
- Verify dates are in the future.

**Rate limit errors**
- Add delays: `time.sleep(1)` between searches.
- Reduce date ranges.
- Consider upgrading API tier.