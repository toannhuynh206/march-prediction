"""
Team and venue geographic coordinates for travel distance factor.

Provides haversine-based great-circle distance between team home cities
and tournament venue cities.
"""

from math import radians, sin, cos, sqrt, atan2

# --- Team home coordinates (approximate city center lat/lon) ---
# All 68 teams (64 field + 4 First Four play-in extras)
TEAM_HOME_COORDS: dict[str, tuple[float, float]] = {
    # East Region
    "Duke":                (36.0014, -78.9382),   # Durham, NC
    "UConn":               (41.8077, -72.2540),   # Storrs, CT
    "Michigan State":      (42.7018, -84.4822),   # East Lansing, MI
    "Kansas":              (38.9543, -95.2558),   # Lawrence, KS
    "St. John's":          (40.7282, -73.7949),   # Queens, NY
    "Louisville":          (38.2527, -85.7585),   # Louisville, KY
    "UCLA":                (34.0689, -118.4452),  # Los Angeles, CA
    "Ohio State":          (39.9988, -83.0178),   # Columbus, OH
    "TCU":                 (32.7097, -97.3633),   # Fort Worth, TX
    "UCF":                 (28.6024, -81.2001),   # Orlando, FL
    "South Florida":       (28.0587, -82.4139),   # Tampa, FL
    "Northern Iowa":       (42.5134, -92.4631),   # Cedar Falls, IA
    "Cal Baptist":         (33.9294, -117.4028),  # Riverside, CA
    "North Dakota State":  (46.8772, -96.7898),   # Fargo, ND
    "Furman":              (34.8507, -82.3940),   # Greenville, SC
    "Siena":               (42.7186, -73.7527),   # Loudonville, NY

    # South Region
    "Florida":             (29.6516, -82.3248),   # Gainesville, FL
    "Houston":             (29.7193, -95.3422),   # Houston, TX
    "Illinois":            (40.1020, -88.2272),   # Champaign, IL
    "Nebraska":            (40.8202, -96.7005),   # Lincoln, NE
    "Vanderbilt":          (36.1447, -86.8027),   # Nashville, TN
    "North Carolina":      (35.9049, -79.0469),   # Chapel Hill, NC
    "Saint Mary's":        (37.8407, -122.1118),  # Moraga, CA
    "Clemson":             (34.6834, -82.8374),   # Clemson, SC
    "Iowa":                (41.6611, -91.5302),   # Iowa City, IA
    "Texas A&M":           (30.6280, -96.3344),   # College Station, TX
    "VCU":                 (37.5488, -77.4530),   # Richmond, VA
    "McNeese":             (30.2091, -93.2083),   # Lake Charles, LA
    "Troy":                (31.7990, -85.9697),   # Troy, AL
    "Penn":                (39.9522, -75.1932),   # Philadelphia, PA
    "Idaho":               (46.7324, -117.0002),  # Moscow, ID
    "Prairie View A&M":    (30.0900, -95.9863),   # Prairie View, TX
    "Lehigh":              (40.6084, -75.3781),   # Bethlehem, PA

    # West Region
    "Arizona":             (32.2319, -110.9501),  # Tucson, AZ
    "Purdue":              (40.4237, -86.9212),   # West Lafayette, IN
    "Gonzaga":             (47.6670, -117.4025),  # Spokane, WA
    "Arkansas":            (36.0822, -94.1719),   # Fayetteville, AR
    "Wisconsin":           (43.0731, -89.4012),   # Madison, WI
    "BYU":                 (40.2338, -111.6585),  # Provo, UT
    "Miami":               (25.7214, -80.2793),   # Coral Gables, FL
    "Villanova":           (40.0344, -75.3369),   # Villanova, PA
    "Utah State":          (41.7370, -111.8338),  # Logan, UT
    "Missouri":            (38.9404, -92.3277),   # Columbia, MO
    "Texas":               (30.2849, -97.7341),   # Austin, TX
    "NC State":            (35.7847, -78.6821),   # Raleigh, NC
    "High Point":          (35.9557, -80.0053),   # High Point, NC
    "Hawaii":              (21.2969, -157.8171),  # Honolulu, HI
    "Kennesaw State":      (34.0382, -84.5816),   # Kennesaw, GA
    "Queens":              (35.2271, -80.8431),   # Charlotte, NC
    "LIU":                 (40.6892, -73.9857),   # Brooklyn, NY

    # Midwest Region
    "Michigan":            (42.2808, -83.7430),   # Ann Arbor, MI
    "Iowa State":          (42.0266, -93.6465),   # Ames, IA
    "Virginia":            (38.0336, -78.5080),   # Charlottesville, VA
    "Alabama":             (33.2098, -87.5692),   # Tuscaloosa, AL
    "Texas Tech":          (33.5843, -101.8456),  # Lubbock, TX
    "Tennessee":           (35.9544, -83.9295),   # Knoxville, TN
    "Kentucky":            (38.0406, -84.5037),   # Lexington, KY
    "Georgia":             (33.9480, -83.3773),   # Athens, GA
    "Saint Louis":         (38.6270, -90.1994),   # St. Louis, MO
    "Santa Clara":         (37.3541, -121.9552),  # Santa Clara, CA
    "Miami (OH)":          (39.5070, -84.7452),   # Oxford, OH
    "SMU":                 (32.8431, -96.7850),   # Dallas, TX
    "Akron":               (41.0814, -81.5190),   # Akron, OH
    "Hofstra":             (40.7138, -73.5999),   # Hempstead, NY
    "Wright State":        (39.7813, -84.0625),   # Dayton, OH
    "Tennessee State":     (36.1670, -86.8320),   # Nashville, TN
    "UMBC":                (39.2554, -76.7108),   # Catonsville, MD
    "Howard":              (38.9219, -77.0199),   # Washington, DC
}


# --- Tournament venue coordinates ---
VENUE_COORDS: dict[str, tuple[float, float]] = {
    # First Four
    "Dayton, OH":          (39.7589, -84.1916),

    # First/Second Round sites
    "Greenville, SC":      (34.8526, -82.3940),
    "Buffalo, NY":         (42.8864, -78.8784),
    "Oklahoma City, OK":   (35.4676, -97.5164),
    "Portland, OR":        (45.5152, -122.6784),
    "Tampa, FL":           (27.9506, -82.4572),
    "Philadelphia, PA":    (39.9526, -75.1652),
    "San Diego, CA":       (32.7157, -117.1611),
    "St. Louis, MO":       (38.6270, -90.1994),

    # Regional sites
    "Washington, DC":      (38.8977, -77.0365),
    "Houston, TX":         (29.7604, -95.3698),
    "San Jose, CA":        (37.3382, -121.8863),
    "Chicago, IL":         (41.8781, -87.6298),

    # Final Four
    "Indianapolis, IN":    (39.7684, -86.1581),
}


# Earth's mean radius in miles
_EARTH_RADIUS_MILES = 3958.8


def travel_distance_miles(team_name: str, venue_city: str) -> float:
    """Compute great-circle distance (miles) between a team's home and a venue.

    Uses the haversine formula for accuracy on a spherical Earth.

    Args:
        team_name: Exact team name as it appears in TEAM_HOME_COORDS.
        venue_city: Venue city string as it appears in VENUE_COORDS
                    (e.g. "Greenville, SC").

    Returns:
        Distance in miles (float).

    Raises:
        KeyError: If team_name or venue_city is not found in the lookup dicts.
    """
    if team_name not in TEAM_HOME_COORDS:
        raise KeyError(
            f"Unknown team: '{team_name}'. "
            f"Available teams: {sorted(TEAM_HOME_COORDS.keys())}"
        )
    if venue_city not in VENUE_COORDS:
        raise KeyError(
            f"Unknown venue: '{venue_city}'. "
            f"Available venues: {sorted(VENUE_COORDS.keys())}"
        )

    lat1, lon1 = TEAM_HOME_COORDS[team_name]
    lat2, lon2 = VENUE_COORDS[venue_city]

    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return _EARTH_RADIUS_MILES * c


if __name__ == "__main__":
    # Quick sanity check
    print(f"Teams in database: {len(TEAM_HOME_COORDS)}")
    print(f"Venues in database: {len(VENUE_COORDS)}")
    print()

    # Sample distances
    samples = [
        ("Duke", "Greenville, SC"),
        ("Hawaii", "San Diego, CA"),
        ("Kansas", "Indianapolis, IN"),
        ("Gonzaga", "Portland, OR"),
        ("Florida", "Tampa, FL"),
        ("Michigan", "Chicago, IL"),
    ]
    for team, venue in samples:
        dist = travel_distance_miles(team, venue)
        print(f"  {team:20s} -> {venue:20s} = {dist:,.0f} miles")
