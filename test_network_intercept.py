#!/usr/bin/env python3
"""
Test script to intercept Google Flights network requests
This will show us what internal APIs Google Flights uses
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def intercept_google_flights():
    """Monitor network requests to find Google Flights' internal API"""

    # Store intercepted requests
    api_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Intercept all requests
        async def handle_request(request):
            # Look for API calls (usually to /rpc/ or containing JSON)
            if any(keyword in request.url for keyword in ['/rpc/', 'FlightsFrontend', '_/rpc/', 'batchexecute']):
                print(f"\n{'='*80}")
                print(f"API REQUEST FOUND:")
                print(f"URL: {request.url}")
                print(f"Method: {request.method}")
                print(f"Resource Type: {request.resource_type}")

                # Try to get post data
                try:
                    post_data = request.post_data
                    if post_data:
                        print(f"POST Data (first 500 chars): {post_data[:500]}")
                except:
                    pass

                api_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'type': request.resource_type
                })

        # Intercept responses too
        async def handle_response(response):
            if any(keyword in response.url for keyword in ['/rpc/', 'FlightsFrontend', '_/rpc/', 'batchexecute']):
                print(f"\nAPI RESPONSE:")
                print(f"URL: {response.url}")
                print(f"Status: {response.status}")

                try:
                    # Try to get response body
                    body = await response.text()
                    print(f"Response (first 500 chars): {body[:500]}")
                except Exception as e:
                    print(f"Could not read response: {e}")

        page.on('request', handle_request)
        page.on('response', handle_response)

        # Navigate to Google Flights round-trip search
        url = "https://www.google.com/travel/flights?q=Flights%20from%20LHR%20to%20HKG%20on%202026-02-05%20returning%202026-02-15&hl=en&curr=GBP"

        print(f"\n{'='*80}")
        print(f"Loading Google Flights...")
        print(f"URL: {url}")
        print(f"{'='*80}\n")

        await page.goto(url, wait_until='networkidle', timeout=60000)

        # Handle cookie dialog
        try:
            reject_button = await page.query_selector('button:has-text("Reject all")')
            if reject_button:
                await reject_button.click()
                await asyncio.sleep(2)
        except:
            pass

        # Wait for results to load
        print("\nWaiting 20 seconds for all API calls...")
        await asyncio.sleep(20)

        # Save findings
        print(f"\n{'='*80}")
        print(f"SUMMARY:")
        print(f"Found {len(api_requests)} API requests")
        print(f"{'='*80}\n")

        with open("google_flights_api_requests.json", "w") as f:
            json.dump(api_requests, f, indent=2)

        print("Saved API request details to google_flights_api_requests.json")
        print("\nPress Enter to close browser...")
        input()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_google_flights())
