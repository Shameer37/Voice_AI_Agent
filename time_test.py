from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+

def utc_to_ist(utc_iso: str) -> str:
    """
    Converts ISO-8601 UTC timestamp to IST string.
    """
    utc_dt = datetime.fromisoformat(
        utc_iso.replace("Z", "+00:00")
    )
    ist_dt = utc_dt.astimezone(ZoneInfo("Asia/Kolkata"))

    return ist_dt.strftime("%d-%b-%Y %I:%M:%S %p IST")

print(utc_to_ist("2026-01-29T09:45:47.947Z"))  # Example usage