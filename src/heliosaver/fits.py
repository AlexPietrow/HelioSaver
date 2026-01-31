from __future__ import annotations

import io
import os
from typing import Dict, List, Optional, Union
from xml.etree import ElementTree as ET

import imageio.v3 as iio
import numpy as np
from astropy.io import fits

from .hv_api import get_closest_image_id, get_jp2_header_text, get_jp2_image_bytes


def jp2_bytes_to_numpy(jp2_bytes: bytes) -> np.ndarray:
    """Decode JP2 bytes into a numpy array using imageio.

    Raises
    ------
    RuntimeError
        If decoding fails.
    """
    try:
        img = iio.imread(io.BytesIO(jp2_bytes), extension=".jp2")
        return np.asarray(img)
    except Exception as e:
        raise RuntimeError(f"Failed to decode JP2: {e}") from e


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


def process_helioviewer_fits(
    dates: Union[str, List[str]],
    source_id: int,
    output_path: str = ".",
    save_header_txt: bool = True,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Closest-image pipeline: download JP2 + header, then write FITS.

    Parameters
    ----------
    dates
        A single ISO8601 date string or a list of them.
    source_id
        Helioviewer sourceId.
    output_path
        Directory where files are written.
    save_header_txt
        If True, also save the raw header XML as a .txt file.

    Returns
    -------
    dict
        {date: {"header_txt": path|None, "fits": path|None}}
    """
    os.makedirs(output_path, exist_ok=True)
    if isinstance(dates, str):
        dates = [dates]

    out: Dict[str, Dict[str, Optional[str]]] = {}

    for date in dates:
        image_id = get_closest_image_id(date, source_id)
        if image_id is None:
            out[date] = {"header_txt": None, "fits": None}
            continue

        jp2_bytes = get_jp2_image_bytes(image_id)
        header_text = get_jp2_header_text(image_id)

        if jp2_bytes is None or header_text is None:
            out[date] = {"header_txt": None, "fits": None}
            continue

        header_txt_path = None
        if save_header_txt:
            header_txt_path = os.path.join(output_path, f"helioviewer_{image_id}.xml.txt")
            with open(header_txt_path, "w", encoding="utf-8") as f:
                f.write(header_text)

        img = jp2_bytes_to_numpy(jp2_bytes)
        hdr = header_xml_to_fits_header(header_text)

        stem = date.replace(":", "").replace("T", "_")
        fits_path = os.path.join(output_path, f"helioviewer_{stem}_source_{source_id}.fits")

        image_hdu = fits.ImageHDU(data=img, header=hdr, name="JP2_IMAGE")
        hdul = fits.HDUList([fits.PrimaryHDU(), image_hdu])
        hdul.writeto(fits_path, overwrite=True)

        out[date] = {"header_txt": header_txt_path, "fits": fits_path}

    return out
