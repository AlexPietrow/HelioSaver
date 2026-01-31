from __future__ import annotations
from typing import Optional, Tuple
import requests

BASE_URL = "https://api.helioviewer.org/v2/"



def get_closest_image_id(date: str, source_id: int, timeout: float = 60.0) -> Optional[int]:
    """Return the closest available Helioviewer image id for a date/source.

    Parameters
    ----------
    date
        ISO8601 with Z recommended, e.g. "2014-01-01T23:59:59Z"
    source_id
        Helioviewer sourceId.
    timeout
        Requests timeout in seconds.

    Returns
    -------
    int | None
        Image id if found, otherwise None.
    """
    url = f"{BASE_URL}getClosestImage/"
    r = requests.get(url, params={"date": date, "sourceId": source_id}, timeout=timeout)
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("id")

def get_closest_image(date: str, source_id: int, timeout: float = 60.0) -> Tuple[Optional[int], Optional[str]]:
    """
    Returns (image_id, closest_date_str) where closest_date_str is like "YYYY-MM-DD HH:MM:SS" (UTC).
    """
    url = f"{BASE_URL}getClosestImage/"
    r = requests.get(url, params={"date": date, "sourceId": source_id}, timeout=timeout)
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("id"), data.get("date")



def get_jp2_image_bytes(image_id: int, timeout: float = 120.0) -> Optional[bytes]:
    """Download JP2 bytes for a given Helioviewer image id."""
    url = f"{BASE_URL}getJP2Image/"
    r = requests.get(url, params={"id": image_id}, timeout=timeout)
    if r.status_code != 200:
        return None
    return r.content


def get_jp2_header_text(image_id: int, timeout: float = 60.0) -> Optional[str]:
    """Download JP2 header (XML string) for a given Helioviewer image id."""
    url = f"{BASE_URL}getJP2Header/"
    r = requests.get(url, params={"id": image_id}, timeout=timeout)
    if r.status_code != 200:
        return None
    return r.text
