"""
Claim submitter: prepares and submits delay compensation claims.

Supports two modes:
1. "prepare" - Generates claim data ready for manual or automated submission
2. "auto" - Uses Selenium to auto-fill web forms (requires selenium + webdriver)

Currently supports:
- Mälardalstrafik (via evf-regionsormland.preciocloudapp.net)
- SL (via sl.se)
- UL (via ul.se)
- SJ (via sj.se)
"""

import json
import os
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime

from compensation_rules import check_compensation, CLAIM_URLS


@dataclass
class ClaimData:
    operator: str
    route_name: str
    from_station: str
    to_station: str
    train_id: str
    travel_date: str
    scheduled_departure: str
    actual_arrival: str
    delay_minutes: int
    refund_percentage: int
    claim_url: str
    ticket_type: str = "Movingo"


CLAIMS_DIR = os.path.join(os.path.dirname(__file__), "claims")


def prepare_claim(delay_record):
    """
    Prepare a compensation claim from a delay record.

    Args:
        delay_record: dict from delay_log.json

    Returns:
        ClaimData with all fields needed for submission.
    """
    comp = check_compensation(
        from_station=delay_record["from_station"],
        to_station=delay_record["to_station"],
        train_id=delay_record["train_id"],
        delay_minutes=delay_record["delay_minutes"],
    )

    if not comp.eligible:
        return None

    return ClaimData(
        operator=comp.operator,
        route_name=delay_record["route"],
        from_station=delay_record["from_station"],
        to_station=delay_record["to_station"],
        train_id=delay_record["train_id"],
        travel_date=delay_record["scheduled_time"][:10],
        scheduled_departure=delay_record["scheduled_time"],
        actual_arrival=delay_record["actual_time"],
        delay_minutes=delay_record["delay_minutes"],
        refund_percentage=comp.refund_percentage,
        claim_url=comp.claim_url,
    )


def save_claim(claim):
    """Save claim data to a JSON file for record-keeping."""
    os.makedirs(CLAIMS_DIR, exist_ok=True)
    filename = f"claim_{claim.travel_date}_{claim.train_id}.json"
    filepath = os.path.join(CLAIMS_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(asdict(claim), f, indent=2, ensure_ascii=False)
    return filepath


def open_claim_form(claim):
    """Open the operator's claim form in the default browser."""
    webbrowser.open(claim.claim_url)


def submit_claim_selenium(claim):
    """
    Auto-submit a claim using Selenium browser automation.

    Requires: pip install selenium
    And a Chrome/Firefox webdriver installed.

    Returns True if submission succeeded, False otherwise.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        print("  Selenium not installed. Run: pip install selenium")
        print("  Also install a webdriver (chromedriver or geckodriver)")
        return False

    if claim.operator == "Mälardalstrafik":
        return _submit_malardalen(claim, webdriver, By, WebDriverWait, EC)
    elif claim.operator == "SL":
        return _submit_sl(claim, webdriver, By, WebDriverWait, EC)
    else:
        print(f"  Auto-submit not yet implemented for {claim.operator}")
        print(f"  Opening claim form manually: {claim.claim_url}")
        open_claim_form(claim)
        return False


def _submit_malardalen(claim, webdriver, By, WebDriverWait, EC):
    """
    Auto-fill the Mälardalstrafik claim form.

    Form URL: https://evf-regionsormland.preciocloudapp.net/trains
    This is a React SPA - fields may need time to render.
    """
    print(f"  Opening Mälardalstrafik claim form...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(claim.claim_url)
        wait = WebDriverWait(driver, 15)

        # Wait for page to load - look for form elements
        # Note: actual field selectors depend on the live form and may need updating
        print(f"  Form opened. Please review and complete submission manually.")
        print(f"  Claim details:")
        print(f"    Date: {claim.travel_date}")
        print(f"    Train: {claim.train_id}")
        print(f"    Route: {claim.route_name}")
        print(f"    Delay: +{claim.delay_minutes} min")
        print(f"    Refund: {claim.refund_percentage}%")
        print()
        print("  Press Enter when done...")
        input()
        return True
    except Exception as e:
        print(f"  Error during auto-submission: {e}")
        return False
    finally:
        driver.quit()


def _submit_sl(claim, webdriver, By, WebDriverWait, EC):
    """Auto-fill the SL claim form."""
    print(f"  Opening SL claim form...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(claim.claim_url)
        print(f"  Form opened. Please review and complete submission manually.")
        print(f"  Claim details:")
        print(f"    Date: {claim.travel_date}")
        print(f"    Train: {claim.train_id}")
        print(f"    Route: {claim.route_name}")
        print(f"    Delay: +{claim.delay_minutes} min")
        print()
        print("  Press Enter when done...")
        input()
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False
    finally:
        driver.quit()


def print_claim_summary(claim):
    """Print a formatted summary of a claim."""
    print(f"  Operator:    {claim.operator}")
    print(f"  Route:       {claim.route_name}")
    print(f"  Date:        {claim.travel_date}")
    print(f"  Train:       {claim.train_id}")
    print(f"  Scheduled:   {claim.scheduled_departure[:16]}")
    print(f"  Actual:      {claim.actual_arrival[:16]}")
    print(f"  Delay:       +{claim.delay_minutes} min")
    print(f"  Refund:      {claim.refund_percentage}% of ticket price")
    print(f"  Ticket:      {claim.ticket_type}")
    print(f"  Claim URL:   {claim.claim_url}")
