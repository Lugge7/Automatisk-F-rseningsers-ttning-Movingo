"""
Find train delays >20 minutes from Stockholm C to Bålsta and Uppsala C.

NOTE: Trafikverket's API only retains ~3 days of historical TrainAnnouncement
data, so "last 30 days" will only return results for the available window.

Strategy: Query arrivals at the destination station for trains coming
from the Stockholm direction to capture actual delay at destination.
"""

import requests
from datetime import datetime, timedelta

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
API_KEY = "3d8f864a01f5401798dc1fc2126b3f0c"

# Trains from Stockholm direction: check FromLocation signature
# Includes Stockholm C (Cst), Stockholm City (Sci), Stockholms S (Sst),
# Nynäshamn/pendeltåg origins (Nyc), Västerhaninge (Vhe), etc.
STOCKHOLM_ORIGINS = {"Cst", "Sci", "Nyc", "Sst", "Vhe", "Sod"}

ROUTES = [
    {"name": "Stockholm C → Bålsta", "arrival_station": "Bål"},
    {"name": "Stockholm C → Uppsala C", "arrival_station": "U"},
]

MIN_DELAY_MINUTES = 20


def fetch_arrivals(station, date_from, date_to, limit=10000):
    """Fetch all arrivals at a station over a date range in 1-day chunks."""
    all_announcements = []
    current = date_from

    while current < date_to:
        chunk_end = min(current + timedelta(days=1), date_to)
        t_from = current.strftime("%Y-%m-%dT00:00:00")
        t_to = chunk_end.strftime("%Y-%m-%dT23:59:59")

        xml = f"""<REQUEST>
  <LOGIN authenticationkey="{API_KEY}" />
  <QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="{limit}" orderby="AdvertisedTimeAtLocation asc">
    <FILTER>
      <AND>
        <EQ name="ActivityType" value="Ankomst" />
        <EQ name="LocationSignature" value="{station}" />
        <GTE name="AdvertisedTimeAtLocation" value="{t_from}" />
        <LTE name="AdvertisedTimeAtLocation" value="{t_to}" />
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
        announcements = result[0].get("TrainAnnouncement", []) if result else []
        all_announcements.extend(announcements)
        current = chunk_end + timedelta(seconds=1)

    return all_announcements


def compute_delay_minutes(scheduled_str, actual_str):
    try:
        sched = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))
        actual = datetime.fromisoformat(actual_str.replace("Z", "+00:00"))
        return (actual - sched).total_seconds() / 60
    except (ValueError, TypeError):
        return 0


def main():
    now = datetime.utcnow()
    date_from = now - timedelta(days=30)
    date_to = now

    print("=" * 95)
    print(f"  TRAIN DELAYS > {MIN_DELAY_MINUTES} MIN  |  Querying {date_from.strftime('%Y-%m-%d')} → {date_to.strftime('%Y-%m-%d')}")
    print(f"  NOTE: Trafikverket API only retains ~3 days of historical data")
    print("=" * 95)

    for route in ROUTES:
        print(f"\n{'─' * 95}")
        print(f"  Route: {route['name']}")
        print(f"{'─' * 95}\n")

        arrivals = fetch_arrivals(
            station=route["arrival_station"],
            date_from=date_from,
            date_to=date_to,
        )

        # Filter: only trains coming from the Stockholm direction
        relevant = []
        for ann in arrivals:
            from_locs = ann.get("FromLocation", [])
            origins = {loc.get("LocationName", "") for loc in from_locs}
            if origins & STOCKHOLM_ORIGINS:
                relevant.append(ann)

        delayed = []
        canceled_count = 0
        total_with_actual = 0

        for ann in relevant:
            if ann.get("Canceled", False):
                canceled_count += 1
                continue

            scheduled = ann.get("AdvertisedTimeAtLocation", "")
            actual = ann.get("TimeAtLocation", "")

            if scheduled and actual:
                total_with_actual += 1
                delay = compute_delay_minutes(scheduled, actual)
                if delay > MIN_DELAY_MINUTES:
                    delayed.append({
                        "train": ann.get("AdvertisedTrainIdent", "?"),
                        "scheduled": scheduled,
                        "actual": actual,
                        "delay_min": int(delay),
                    })

        delayed.sort(key=lambda x: x["delay_min"], reverse=True)

        if relevant:
            first_date = min(a.get("AdvertisedTimeAtLocation","")[:10] for a in relevant)
            last_date = max(a.get("AdvertisedTimeAtLocation","")[:10] for a in relevant)
            print(f"  Data available:                     {first_date} → {last_date}")
        else:
            print(f"  Data available:                     (none)")
        print(f"  Total arrivals from Stockholm dir:  {len(relevant)}")
        print(f"  Arrived (with actual time):         {total_with_actual}")
        print(f"  Canceled:                           {canceled_count}")
        print(f"  Delayed > {MIN_DELAY_MINUTES} min:                  {len(delayed)}")
        print()

        if delayed:
            print(f"  {'Date':<12} {'Sched':>5} {'Actual':>7} {'Delay':>9}  {'Train':>6}")
            print(f"  {'─'*12} {'─'*5} {'─'*7} {'─'*9}  {'─'*6}")
            for d in delayed:
                date_str = d["scheduled"][:10]
                sched_time = d["scheduled"][11:16]
                actual_time = d["actual"][11:16]
                delay_str = f"+{d['delay_min']} min"
                print(f"  {date_str:<12} {sched_time:>5} {actual_time:>7} {delay_str:>9}  {d['train']:>6}")
        else:
            print("  No delays > 20 min found.")

        print()

    print("=" * 95)


if __name__ == "__main__":
    main()
