from langchain_core.tools import tool


CATEGORY_WEIGHTS = {
    "accommodation": 0.35,
    "food": 0.25,
    "activities": 0.25,
    "transport": 0.15,
}


@tool
def allocate_budget(
    total_budget: float, num_days: int, num_travelers: int, currency: str
) -> str:
    """Allocate a travel budget across days and categories.
    Splits budget into accommodation, food, activities, and transport.
    Returns per-day and per-person breakdown.
    """
    if num_days <= 0 or num_travelers <= 0 or total_budget <= 0:
        return "Invalid input: all values must be positive"

    daily_budget = total_budget / num_days
    per_person_daily = daily_budget / num_travelers

    lines = [
        f"Total Budget: {total_budget:.2f} {currency}",
        f"Daily Budget: {daily_budget:.2f} {currency} ({per_person_daily:.2f}/person)",
        "",
        "Category Breakdown (per day):",
    ]

    for category, weight in CATEGORY_WEIGHTS.items():
        amount = daily_budget * weight
        per_person = amount / num_travelers
        lines.append(f"  {category}: {amount:.2f} {currency} ({per_person:.2f}/person)")

    lines.append("")
    lines.append("Day-by-day allocation:")
    for day in range(1, num_days + 1):
        lines.append(f"  Day {day}: {daily_budget:.2f} {currency}")

    return "\n".join(lines)
