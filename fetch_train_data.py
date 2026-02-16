"""
Fetch train announcement data from Trafikverket's open API.

Uses the TrainAnnouncement object type to get timetable information
about trains at stations/stops.
"""

import requests
from datetime import datetime, timedelta

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
API_KEY = "3d8f864a01f5401798dc1fc2126b3f0c"


def build_request_xml(api_key, object_type, schema_version, filters="", includes="", limit=20):
    """Build the XML request body for the Trafikverket API."""
    include_section = ""
    if includes:
        include_section = "\n".join(f'      <INCLUDE>{field}</INCLUDE>' for field in includes)
        include_section = f"\n{include_section}"

    filter_section = ""
    if filters:
        filter_section = f"\n    <FILTER>\n{filters}\n    </FILTER>"

    return f"""<REQUEST>
  <LOGIN authenticationkey="{api_key}" />
  <QUERY objecttype="{object_type}" schemaversion="{schema_version}" limit="{limit}">{filter_section}{include_section}
  </QUERY>
</REQUEST>"""


def fetch_train_announcements(station_code=None, limit=20):
    """
    Fetch TrainAnnouncement data from Trafikverket.

    Args:
        station_code: Optional station signature (e.g., "Cst" for Stockholm Central).
                      If None, fetches recent announcements.
        limit: Maximum number of results to return.

    Returns:
        List of train announcement dicts.
    """
    now = datetime.utcnow()
    time_from = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
    time_to = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

    filters = f'      <GTE name="AdvertisedTimeAtLocation" value="{time_from}" />\n'
    filters += f'      <LTE name="AdvertisedTimeAtLocation" value="{time_to}" />'

    if station_code:
        filters += f'\n      <EQ name="LocationSignature" value="{station_code}" />'

    includes = [
        "AdvertisedTrainIdent",
        "LocationSignature",
        "AdvertisedTimeAtLocation",
        "TimeAtLocation",
        "ActivityType",
        "TrackAtLocation",
        "ToLocation",
        "FromLocation",
        "Canceled",
        "EstimatedTimeAtLocation",
    ]

    xml_body = build_request_xml(
        api_key=API_KEY,
        object_type="TrainAnnouncement",
        schema_version="1.9",
        filters=filters,
        includes=includes,
        limit=limit,
    )

    response = requests.post(
        API_URL,
        data=xml_body,
        headers={"Content-Type": "text/xml"},
    )
    response.raise_for_status()

    data = response.json()
    result = data.get("RESPONSE", {}).get("RESULT", [])
    if result:
        return result[0].get("TrainAnnouncement", [])
    return []


def fetch_train_stations(limit=50):
    """Fetch TrainStation data from Trafikverket."""
    includes = [
        "AdvertisedLocationName",
        "LocationSignature",
        "CountyNo",
    ]

    xml_body = build_request_xml(
        api_key=API_KEY,
        object_type="TrainStation",
        schema_version="1.4",
        includes=includes,
        limit=limit,
    )

    response = requests.post(
        API_URL,
        data=xml_body,
        headers={"Content-Type": "text/xml"},
    )
    response.raise_for_status()

    data = response.json()
    result = data.get("RESPONSE", {}).get("RESULT", [])
    if result:
        return result[0].get("TrainStation", [])
    return []


def format_announcement(ann):
    """Format a single train announcement for display."""
    train_id = ann.get("AdvertisedTrainIdent", "?")
    station = ann.get("LocationSignature", "?")
    activity = ann.get("ActivityType", "?")
    scheduled = ann.get("AdvertisedTimeAtLocation", "")
    actual = ann.get("TimeAtLocation", "")
    estimated = ann.get("EstimatedTimeAtLocation", "")
    canceled = ann.get("Canceled", False)
    track = ann.get("TrackAtLocation", "?")

    to_locations = ann.get("ToLocation", [])
    to_str = ", ".join(loc.get("LocationName", "") for loc in to_locations) if to_locations else "-"

    scheduled_short = scheduled[11:16] if len(scheduled) > 16 else scheduled
    actual_short = actual[11:16] if len(actual) > 16 else actual or "-"
    estimated_short = estimated[11:16] if len(estimated) > 16 else estimated or "-"

    status = "CANCELED" if canceled else "OK"
    if actual and scheduled and not canceled:
        try:
            sched_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            actual_dt = datetime.fromisoformat(actual.replace("Z", "+00:00"))
            delay_min = (actual_dt - sched_dt).total_seconds() / 60
            if delay_min > 1:
                status = f"DELAYED +{int(delay_min)}min"
        except (ValueError, TypeError):
            pass
    elif estimated and scheduled and not canceled:
        try:
            sched_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            est_dt = datetime.fromisoformat(estimated.replace("Z", "+00:00"))
            delay_min = (est_dt - sched_dt).total_seconds() / 60
            if delay_min > 1:
                status = f"EST. DELAYED +{int(delay_min)}min"
        except (ValueError, TypeError):
            pass

    activity_label = "DEP" if activity == "Avgang" else "ARR"

    return (
        f"  Train {train_id:>6} | {activity_label} {station:>4} spår {track:>2} | "
        f"Scheduled: {scheduled_short} | Actual: {actual_short} | Est: {estimated_short} | "
        f"To: {to_str:<12} | {status}"
    )


if __name__ == "__main__":
    print("=" * 100)
    print("TRAFIKVERKET TRAIN DATA")
    print("=" * 100)

    # Fetch train announcements (Stockholm Central = "Cst")
    print("\n--- Train Announcements (Stockholm Central) ---\n")
    try:
        announcements = fetch_train_announcements(station_code="Cst", limit=20)
        if announcements:
            for ann in announcements:
                print(format_announcement(ann))
        else:
            print("  No announcements found for the requested time window.")
    except requests.exceptions.HTTPError as e:
        print(f"  API error: {e}")
        print(f"  Response: {e.response.text if e.response else 'N/A'}")

    # Fetch some train stations
    print("\n--- Sample Train Stations ---\n")
    try:
        stations = fetch_train_stations(limit=10)
        for s in stations:
            name = s.get("AdvertisedLocationName", "?")
            sig = s.get("LocationSignature", "?")
            print(f"  {name:<30} ({sig})")
    except requests.exceptions.HTTPError as e:
        print(f"  API error: {e}")

    print("=" * 100)
