"""
Compensation rules for Swedish train operators.

Defines delay thresholds and refund percentages for:
- UL (Uppsala Lokaltrafik)
- SL (Stockholms Lokaltrafik)
- Mälardalstrafik (Mälartåg)
- SJ

References:
  https://www.ul.se/kundservice/forseningsersattning/
  https://sl.se/kundservice/forseningsersattning
  https://www.malardalstrafik.se/kundservice/ersaettning-vid-foersening/
  https://www.sj.se/om-sj/regler-och-villkor/rattigheter-vid-forsening
"""

from dataclasses import dataclass

# Compensation tiers: (min_delay_minutes, refund_percentage)
# Listed in descending order so the first match wins.

UL_TIERS = [
    (60, 100),
    (40, 75),
    (20, 50),
]

SL_TIERS = [
    (60, 100),
    (20, 50),
]

# Mälardalstrafik for trips under 150 km (Stockholm-Bålsta ~60km, Stockholm-Uppsala ~70km)
MALARDALEN_SHORT_TIERS = [
    (60, 100),
    (40, 75),
    (20, 50),
]

# Mälardalstrafik for trips 150 km or longer
MALARDALEN_LONG_TIERS = [
    (120, 50),
    (60, 25),
]

# SJ for trips under 150 km
SJ_SHORT_TIERS = [
    (60, 100),
    (20, 50),
]

# SJ for trips 150 km or longer
SJ_LONG_TIERS = [
    (120, 50),
    (60, 25),
]

# Max reimbursement for alternative transport (2026)
ALT_TRANSPORT_MAX_SEK = 1480

# Claim deadlines (days)
CLAIM_DEADLINES = {
    "UL": 60,        # 2 months
    "SL": 90,        # 3 months
    "Mälardalstrafik": 90,
    "SJ": 90,
}

# Claim submission URLs
CLAIM_URLS = {
    "UL": "https://www.ul.se/kundservice/forseningsersattning/",
    "SL": "https://sl.se/kundservice/forseningsersattning",
    "Mälardalstrafik": "https://evf-regionsormland.preciocloudapp.net/trains",
    "SJ": "https://www.sj.se/om-sj/regler-och-villkor/rattigheter-vid-forsening",
}


@dataclass
class CompensationResult:
    eligible: bool
    operator: str
    delay_minutes: int
    refund_percentage: int
    claim_url: str
    claim_deadline_days: int
    notes: str = ""


def get_refund_percentage(tiers, delay_minutes):
    """Return refund percentage for a given delay using the operator's tier list."""
    for min_delay, pct in tiers:
        if delay_minutes >= min_delay:
            return pct
    return 0


def determine_operator(from_station, to_station, train_id):
    """
    Determine the train operator based on route and train number.

    Heuristic based on Swedish train numbering:
    - 2500-2599: Mälartåg pendel (Stockholm-Bålsta etc.)
    - 100-199: Mälartåg regional
    - 1-99: SJ snabbtåg/regionaltåg
    - 40xxx: SL pendeltåg (not covered here, different system)
    """
    try:
        tid = int(train_id)
    except (ValueError, TypeError):
        tid = 0

    # Mälartåg commuter trains
    if 2500 <= tid <= 2599:
        return "Mälardalstrafik"

    # Mälartåg regional
    if 100 <= tid <= 199:
        return "Mälardalstrafik"

    # SJ trains (long-distance and regional)
    if 1 <= tid <= 99:
        return "SJ"
    if 900 <= tid <= 999:
        return "SJ"
    if 10000 <= tid <= 19999:
        return "SJ"

    # UL local trains (Uppsala region)
    if to_station == "U" and 8000 <= tid <= 8999:
        return "UL"

    # Default based on route
    route = (from_station, to_station)
    if route in [("Cst", "Bål"), ("Cst", "U")]:
        return "Mälardalstrafik"

    return "Unknown"


def check_compensation(from_station, to_station, train_id, delay_minutes, distance_km=None):
    """
    Check if a delayed train qualifies for compensation.

    Args:
        from_station: Origin station code (e.g. "Cst")
        to_station: Destination station code (e.g. "Bål", "U")
        train_id: Train number/identifier
        delay_minutes: Actual delay in minutes
        distance_km: Route distance in km (defaults based on known routes)

    Returns:
        CompensationResult with eligibility details.
    """
    if distance_km is None:
        known_distances = {
            ("Cst", "Bål"): 60,
            ("Cst", "U"): 70,
        }
        distance_km = known_distances.get((from_station, to_station), 50)

    operator = determine_operator(from_station, to_station, train_id)
    is_long = distance_km >= 150

    tiers_map = {
        "UL": UL_TIERS,
        "SL": SL_TIERS,
        "Mälardalstrafik": MALARDALEN_LONG_TIERS if is_long else MALARDALEN_SHORT_TIERS,
        "SJ": SJ_LONG_TIERS if is_long else SJ_SHORT_TIERS,
    }

    tiers = tiers_map.get(operator, MALARDALEN_SHORT_TIERS)
    refund_pct = get_refund_percentage(tiers, delay_minutes)

    return CompensationResult(
        eligible=refund_pct > 0,
        operator=operator,
        delay_minutes=delay_minutes,
        refund_percentage=refund_pct,
        claim_url=CLAIM_URLS.get(operator, ""),
        claim_deadline_days=CLAIM_DEADLINES.get(operator, 90),
        notes=f"Distance: {distance_km}km ({'long' if is_long else 'short'} route)",
    )
