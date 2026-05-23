import httpx
from langchain_core.tools import tool

EXCHANGE_API_URL = "https://open.er-api.com/v6/latest"


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies using live exchange rates.
    Useful for converting travel budgets to local destination currency.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return f"{amount:.2f} {from_currency} = {amount:.2f} {to_currency}"

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{EXCHANGE_API_URL}/{from_currency}")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        return f"Currency conversion failed: {e}"

    if data.get("result") != "success":
        return f"API error: {data.get('error-type', 'unknown')}"

    rates = data.get("rates", {})
    if to_currency not in rates:
        return f"Unknown currency code: {to_currency}"

    converted = amount * rates[to_currency]
    rate = rates[to_currency]
    return f"{amount:.2f} {from_currency} = {converted:.2f} {to_currency} (rate: {rate:.4f})"
