# src/heliosaver/fits.py
from __future__ import annotations

import io
import os
from typing import Dict, List, Optional, Union
from xml.etree import ElementTree as ET

import imageio.v3 as iio
import numpy as np
import requests
from astropy.io import fits

from .hv_api import BASE_URL, get_jp2_header_text, get_jp2_image_bytes


def jp2_bytes_to_numpy(jp2_bytes: bytes) -> np.ndarray:
    """Decode JP2 bytes into a numpy array using imageio."""
    img = iio.imread(io.BytesIO(jp2_bytes), extension=".jp2")
    return np.asarray(img)


def _sanitize_fits_value(value: Optional[str]) -> str:
    """Make a value FITS-card friendly (ASCII, no newlines, <=68 chars)."""
    if not value:
        return "N/A"
    value = value.replace("\n", " ").replace("\r", " ").strip()
    return value.encode("ascii", "ignore").decode("ascii")[:68]


def _parse_fits_value(value: Optional[str]):
    """Convert XML text into a FITS-storable primitive."""
    if value is None:
        return "N/A"

    s = value.strip()
    if s.lower() in {"nan", "null", "n/a", ""}:
        return 0
    if s.lower() in {"inf", "+inf"}:
        return 1.0e9
    if s.lower() == "-inf":
        return -1.0e9

    try:
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        return _sanitize_fits_value(s)


def header_xml_to_fits_header(xml_text: str) -> fits.Header:
    """Convert JP2 header XML text into a FITS Header.

    Notes
    -----
    - FITS keyword max length is 8 characters.
    - Keyword collisions are resolved by suffixing with a digit.
    """
    root = ET.fromstring(xml_text)
    hdr = fits.Header()

    for element in root.iter():
        key = element.tag.upper().strip()[:8]
        val = _parse_fits_value(element.text)

        if key in hdr:
            base = key[:7]
            for i in range(10):
                candidate = f"{base}{i}"
                if candidate not in hdr:
                    key = candidate
                    break

        hdr[key] = val

    return hdr


def _slug(s: str) -> str:
    s = s.strip()
    if not s:
        return "source"
    out = []
    for c in s:
        if c.isalnum() or c in "-_":
            out.append(c)
        else:
            out.append("_")
    slug = "".join(out).strip("_")
    return slug or "source"


def _get_closest_image(date: str, source_id: int, timeout: float = 60.0) -> Optional[dict]:
    """Return full getClosestImage JSON (id, date, name, etc.)."""
    r = requests.get(
        f"{BASE_URL}getClosestImage/",
        params={"date": date, "sourceId": source_id},
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    return r.json()


def process_helioviewer_fits(
    dates: Union[str, List[str]],
    source_id: int,
    output_path: str = ".",
    save_header_txt: bool = True,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Closest-image pipeline: download JP2 + header, then write FITS.

    IMPORTANT:
    - The FITS *filename* is based on the actual closest observation time returned
      by Helioviewer (or DATE-OBS fallback), not the requested time.
    - The FITS filename includes the Helioviewer source nickname (e.g. "HMI Int")
      instead of "source_18".
    """
    os.makedirs(output_path, exist_ok=True)
    if isinstance(dates, str):
        dates = [dates]

    out: Dict[str, Dict[str, Optional[str]]] = {}

    for requested_date in dates:
        closest = _get_closest_image(requested_date, source_id)
        if not closest or "id" not in closest:
            out[requested_date] = {"header_txt": None, "fits": None}
            continue

        image_id = int(closest["id"])
        closest_date = str(closest.get("date", "")).strip()  # "YYYY-MM-DD HH:MM:SS"
        source_name = str(closest.get("name", f"source{source_id}")).strip()

        jp2_bytes = get_jp2_image_bytes(image_id)
        header_text = get_jp2_header_text(image_id)

        if jp2_bytes is None or header_text is None:
            out[requested_date] = {"header_txt": None, "fits": None}
            continue

        header_txt_path = None
        if save_header_txt:
            header_txt_path = os.path.join(output_path, f"helioviewer_{image_id}.xml.txt")
            with open(header_txt_path, "w", encoding="utf-8") as f:
                f.write(header_text)

        img = jp2_bytes_to_numpy(jp2_bytes)
        img = np.flipud(img)

        hdr = header_xml_to_fits_header(header_text)
        hdr["FLIPUD"] = True

        # Prefer closest_date from API, else fall back to DATE_OBS from header, else requested_date
        obs_date = closest_date or str(hdr.get("DATE_OBS", requested_date))

        # Normalize to ISO-like with Z for naming
        obs_iso = obs_date.replace(" ", "T")
        if not obs_iso.endswith("Z"):
            obs_iso += "Z"

        stem = obs_iso.replace(":", "").replace("T", "_").replace("Z", "Z")
        name_slug = _slug(source_name)

        fits_path = os.path.join(output_path, f"helioviewer_{stem}_{name_slug}.fits")

        image_hdu = fits.ImageHDU(data=img, header=hdr, name="JP2_IMAGE")
        fits.HDUList([fits.PrimaryHDU(), image_hdu]).writeto(fits_path, overwrite=True)

        out[requested_date] = {"header_txt": header_txt_path, "fits": fits_path}

    return out
