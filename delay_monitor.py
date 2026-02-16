"""
Delay monitor: polls Trafikverket for train delays and stores them in a JSON file.

Designed to run periodically (e.g. via cron every 5 minutes) to build up
historical delay data, since the API only retains ~3 days of data.

Monitors departures from Stockholm C heading to Bålsta and Uppsala.
"""

import json
import os
import requests
from datetime import datetime, timedelta

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
API_KEY = "3d8f864a01f5401798dc1fc2126b3f0c"

DELAY_LOG_FILE = os.path.join(os.path.dirname(__file__), "delay_log.json")

# Routes to monitor: arrivals at destination from Stockholm direction
MONITORED_ROUTES = [
    {
        "name": "Stockholm C → Bålsta",
        "from_station": "Cst",
        "to_station": "Bål",
        "from_origins": {"Cst", "Sci", "Nyc", "Sst", "Vhe", "Sod"},
    },
    {
        "name": "Stockholm C → Uppsala C",
        "from_station": "Cst",
        "to_station": "U",
        "from_origins": {"Cst", "Sci", "Nyc", "Sst"},
    },
]

MIN_DELAY_MINUTES = 20


def fetch_recent_arrivals(station, hours_back=6):
    """Fetch arrivals at a station from the last N hours."""
    now = datetime.utcnow()
    t_from = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
    t_to = now.strftime("%Y-%m-%dT%H:%M:%S")

    xml = f"""<REQUEST>
  <LOGIN authenticationkey="{API_KEY}" />
  <QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="5000" orderby="AdvertisedTimeAtLocation asc">
    <FILTER>
      <AND>
        <EQ name="ActivityType" value="Ankomst" />
        <EQ name="LocationSignature" value="{station}" />
        <GTE name="AdvertisedTimeAtLocation" value="{t_from}" />
        <LTE name="AdvertisedTimeAtLocation" value="{t_to}" />
        <EXISTS name="TimeAtLocation" value="true" />
      </AND>
    </FILTER>
    <INCLUDE>AdvertisedTrainIdent</INCLUDE>
    <INCLUDE>AdvertisedTimeAtLocation</INCLUDE>
    <INCLUDE>TimeAtLocation</INCLUDE>
    <INCLUDE>EstimatedTimeAtLocation</INCLUDE>
    <INCLUDE>FromLocation</INCLUDE>
    <INCLUDE>ToLocation</INCLUDE>
    <INCLUDE>Canceled</INCLUDE>
  </QUERY>
</REQUEST>"""

    resp = requests.post(API_URL, data=xml.encode("utf-8"),
                         headers={"Content-Type": "text/xml; charset=utf-8"})
    resp.raise_for_status()
    data = resp.json()
    result = data.get("RESPONSE", {}).get("RESULT", [])
    return result[0].get("TrainAnnouncement", []) if result else []


def compute_delay(scheduled_str, actual_str):
    """Return delay in minutes."""
    try:
        sched = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))
        actual = datetime.fromisoformat(actual_str.replace("Z", "+00:00"))
        return (actual - sched).total_seconds() / 60
    except (ValueError, TypeError):
        return 0


def load_delay_log():
    """Load existing delay log from disk."""
    if os.path.exists(DELAY_LOG_FILE):
        with open(DELAY_LOG_FILE, "r") as f:
            return json.load(f)
    return {"delays": []}


def save_delay_log(log_data):
    """Save delay log to disk."""
    with open(DELAY_LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def get_existing_keys(log_data):
    """Return set of unique keys for already-logged delays."""
    return {
        (d["train_id"], d["scheduled_time"])
        for d in log_data["delays"]
    }


def poll_delays():
    """
    Poll Trafikverket for recent delays on monitored routes.
    Returns list of new delay records found.
    """
    log_data = load_delay_log()
    existing = get_existing_keys(log_data)
    new_delays = []

    for route in MONITORED_ROUTES:
        arrivals = fetch_recent_arrivals(route["to_station"])

        for ann in arrivals:
            # Filter by origin direction
            from_locs = ann.get("FromLocation", [])
            origins = {loc.get("LocationName", "") for loc in from_locs}
            if not (origins & route["from_origins"]):
                continue

            train_id = ann.get("AdvertisedTrainIdent", "?")
            scheduled = ann.get("AdvertisedTimeAtLocation", "")
            actual = ann.get("TimeAtLocation", "")
            canceled = ann.get("Canceled", False)

            # Skip if already logged
            if (train_id, scheduled) in existing:
                continue

            delay_min = compute_delay(scheduled, actual) if not canceled else 0

            if canceled or delay_min >= MIN_DELAY_MINUTES:
                record = {
                    "route": route["name"],
                    "from_station": route["from_station"],
                    "to_station": route["to_station"],
                    "train_id": train_id,
                    "scheduled_time": scheduled,
                    "actual_time": actual,
                    "delay_minutes": int(delay_min),
                    "canceled": canceled,
                    "detected_at": datetime.utcnow().isoformat(),
                    "claim_status": "pending",
                }
                log_data["delays"].append(record)
                existing.add((train_id, scheduled))
                new_delays.append(record)

    save_delay_log(log_data)
    return new_delays


def get_pending_claims():
    """Return all delays that haven't been claimed yet."""
    log_data = load_delay_log()
    return [d for d in log_data["delays"] if d["claim_status"] == "pending"]


def mark_claimed(train_id, scheduled_time):
    """Mark a delay as claimed."""
    log_data = load_delay_log()
    for d in log_data["delays"]:
        if d["train_id"] == train_id and d["scheduled_time"] == scheduled_time:
            d["claim_status"] = "claimed"
            d["claimed_at"] = datetime.utcnow().isoformat()
    save_delay_log(log_data)


if __name__ == "__main__":
    print("Polling Trafikverket for delays...")
    new = poll_delays()
    if new:
        print(f"\nFound {len(new)} new delay(s):\n")
        for d in new:
            status = "CANCELED" if d["canceled"] else f"+{d['delay_minutes']} min"
            print(f"  {d['route']} | Train {d['train_id']} | {d['scheduled_time'][:16]} | {status}")
    else:
        print("No new qualifying delays found.")

    pending = get_pending_claims()
    print(f"\nTotal pending claims: {len(pending)}")
