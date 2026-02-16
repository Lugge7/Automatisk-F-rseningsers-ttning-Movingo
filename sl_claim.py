"""
Auto-submit delay compensation claims to SL.

SL's compensation system has two parts:
1. Calculator API: https://services.c.web.sl.se/delaycompensationservice/DelayCompensation
2. Submission API: https://mitt.sl.se/delay/delay_compensation (requires BankID auth)

Since the submission requires BankID authentication, this script:
- Calculates the compensation amount via the public API
- Prepares all claim data
- Opens the SL compensation form in the browser with pre-filled context
- Guides the user through the final submission steps

For fully headless submission, Playwright with a real BankID session would be needed.
"""

import json
import webbrowser
import requests
from datetime import datetime

SL_TICKET_PRODUCTS_URL = "https://services.c.web.sl.se/delaycompensationservice/TicketProducts"
SL_COMPENSATION_URL = "https://services.c.web.sl.se/delaycompensationservice/DelayCompensation"
SL_SITES_URL = "https://services.c.web.sl.se/linesandsiteswebservice/SitesWithLines"
SL_FORM_URL = "https://sl.se/kundservice/forseningsersattning/resan"
SL_SUBMIT_URL = "https://mitt.sl.se/delay/delay_compensation"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Origin": "https://sl.se",
    "Referer": "https://sl.se/kundservice/forseningsersattning/resan",
    "Accept": "application/json",
})

# Station name to SL siteId mapping (cached for known stations)
KNOWN_SITES = {
    "Stockholm": 1001080,
    "Bålsta": 5001440,
    "Uppsala": 8000180,
}


def fetch_ticket_products():
    """Fetch available ticket products from SL."""
    resp = SESSION.get(SL_TICKET_PRODUCTS_URL)
    resp.raise_for_status()
    return resp.json()


def search_site(name):
    """Search for a station/site by name."""
    resp = SESSION.get(SL_SITES_URL, params={"searchString": name})
    resp.raise_for_status()
    results = resp.json()
    if results:
        return results[0]["site"]
    return None


def calculate_compensation(product_code):
    """
    Call SL's compensation calculator API.
    Note: This API currently returns 0 for all inputs without auth context.
    The actual amount is calculated server-side during submission.
    """
    resp = SESSION.post(SL_COMPENSATION_URL, json={"productCode": product_code})
    resp.raise_for_status()
    return resp.json()


def submit_claim_interactive(claim_data):
    """
    Guide the user through submitting a claim on SL's website.

    Since SL requires BankID authentication, we can't fully automate this.
    Instead, we prepare all the data and open the form.
    """
    print("\n" + "=" * 70)
    print("  SL DELAY COMPENSATION CLAIM")
    print("=" * 70)

    print(f"\n  Claim details:")
    print(f"    Route:         {claim_data['from_station']} → {claim_data['to_station']}")
    print(f"    Date:          {claim_data['travel_date']}")
    print(f"    Train:         {claim_data['train_id']}")
    print(f"    Scheduled:     {claim_data['scheduled_time']}")
    print(f"    Actual:        {claim_data['actual_time']}")
    print(f"    Delay:         +{claim_data['delay_minutes']} min")
    print(f"    Ticket type:   {claim_data.get('ticket_type', 'Movingo 30-dagar')}")
    print(f"    Product code:  {claim_data.get('product_code', 'MOVUX30D')}")

    # Calculate compensation estimate
    product_code = claim_data.get("product_code", "MOVUX30D")
    try:
        calc = calculate_compensation(product_code)
        if calc.get("amountSek", 0) > 0:
            print(f"    Estimated:     {calc['amountSek']} SEK")
    except Exception:
        pass

    print(f"\n  Steps to submit:")
    print(f"    1. Click the link below to open the SL compensation form")
    print(f"    2. Log in with BankID when prompted")
    print(f"    3. Fill in the form with the details above:")
    print(f"       - Select ticket type: {claim_data.get('ticket_type', 'Movingo 30-dagar')}")
    print(f"       - Travel date: {claim_data['travel_date']}")
    print(f"       - From: {claim_data['from_station']}")
    print(f"       - To: {claim_data['to_station']}")
    print(f"       - Describe the delay: Train {claim_data['train_id']}, +{claim_data['delay_minutes']} min")
    print(f"    4. Enter your bank account details")
    print(f"    5. Submit the claim")

    print(f"\n  Form URL: {SL_FORM_URL}")
    print()

    try:
        open_browser = input("  Open form in browser? [Y/n]: ").strip().lower()
        if open_browser != "n":
            webbrowser.open(SL_FORM_URL)
            print("  Browser opened.")

        submitted = input("\n  Did you submit the claim? [y/N]: ").strip().lower()
        return submitted == "y"
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipped (non-interactive mode).")
        return False


def test_with_fake_data():
    """Test the system with fake data (does not submit anything)."""
    print("\n" + "=" * 70)
    print("  TEST: SL DELAY COMPENSATION - FAKE DATA")
    print("=" * 70)

    fake_claim = {
        "from_station": "Stockholm C",
        "to_station": "Bålsta",
        "travel_date": "2026-02-15",
        "train_id": "2542",
        "scheduled_time": "17:15",
        "actual_time": "17:42",
        "delay_minutes": 27,
        "ticket_type": "30-dagarsbiljett Movingo",
        "product_code": "MOVUX30D",
    }

    print("\n  1. Fetching available ticket products...")
    try:
        products = fetch_ticket_products()
        movingo_products = [p for p in products if "Movingo" in p.get("name", "")]
        print(f"     Found {len(movingo_products)} Movingo products:")
        for p in movingo_products:
            print(f"       {p['productCode']}: {p['name']}")
    except Exception as e:
        print(f"     Error: {e}")

    print("\n  2. Looking up stations...")
    for station_name in ["Stockholm", "Bålsta"]:
        try:
            site = search_site(station_name)
            if site:
                print(f"     {station_name}: siteId={site['siteId']}, name={site['name']}")
        except Exception as e:
            print(f"     {station_name}: Error - {e}")

    print("\n  3. Calculating compensation...")
    try:
        calc = calculate_compensation(fake_claim["product_code"])
        print(f"     API response: {json.dumps(calc)}")
        print(f"     (Note: API returns 0 without auth context - actual amount calculated during submission)")
    except Exception as e:
        print(f"     Error: {e}")

    print("\n  4. Checking submission endpoint (requires BankID)...")
    try:
        resp = SESSION.post(SL_SUBMIT_URL, json=fake_claim)
        print(f"     HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"     Error: {e}")

    print("\n  5. Prepared claim data:")
    print(f"     {json.dumps(fake_claim, indent=6, ensure_ascii=False)}")

    print("\n" + "=" * 70)
    print("  TEST COMPLETE")
    print("  The SL form requires BankID login for actual submission.")
    print(f"  Form URL: {SL_FORM_URL}")
    print("=" * 70)


if __name__ == "__main__":
    test_with_fake_data()
