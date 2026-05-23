from langchain_core.tools import tool
from math import radians, cos, sin, asin, sqrt


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two coordinates."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _nearest_neighbor_order(points: list[dict]) -> list[dict]:
    """Order points using nearest-neighbor heuristic to minimize total travel distance."""
    if len(points) <= 2:
        return points

    remaining = list(range(len(points)))
    order = [remaining.pop(0)]

    while remaining:
        last = order[-1]
        nearest_idx = min(
            remaining,
            key=lambda i: _haversine(
                points[last]["lat"], points[last]["lon"],
                points[i]["lat"], points[i]["lon"],
            ),
        )
        remaining.remove(nearest_idx)
        order.append(nearest_idx)

    return [points[i] for i in order]


SPEED_KMH = {"walking": 5, "driving": 40, "transit": 25}


@tool
def estimate_travel_time(
    locations: list[dict],
    mode: str = "transit",
) -> str:
    """Estimate travel times between a list of locations for a day's itinerary.
    Each location should have: name, lat, lon.
    Optimizes visit order using nearest-neighbor heuristic.
    Mode can be: walking, driving, transit.
    """
    if len(locations) < 2:
        return "Need at least 2 locations to estimate travel time"

    speed = SPEED_KMH.get(mode, SPEED_KMH["transit"])
    ordered = _nearest_neighbor_order(locations)

    lines = [f"Optimized route ({mode}):"]
    total_km = 0.0
    total_min = 0.0

    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        dist = _haversine(a["lat"], a["lon"], b["lat"], b["lon"])
        time_min = (dist / speed) * 60
        total_km += dist
        total_min += time_min
        lines.append(
            f"  {a['name']} -> {b['name']}: {dist:.1f} km, ~{time_min:.0f} min"
        )

    lines.append(f"\nTotal: {total_km:.1f} km, ~{total_min:.0f} min")
    visit_order = " -> ".join(loc["name"] for loc in ordered)
    lines.append(f"Recommended order: {visit_order}")

    return "\n".join(lines)
