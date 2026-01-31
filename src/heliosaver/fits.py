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
    dates: List[str],
    source_id: int,
    output_path: str = ".",
    save_header_txt: bool = True,
    max_time_delta_seconds: Optional[float] = None,
    failed_log_path: Optional[str] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Download JP2 + header for each requested date, convert to FITS, and write to disk.

    New options:
      - max_time_delta_seconds: if set, only download when the Helioviewer "closest image"
        timestamp is within ±max_time_delta_seconds of the requested date.
      - failed_log_path: if set, append skipped/failed requests to this text file.

    Returns
    -------
    dict: {date_str: {"header_txt": <path|None>, "fits": <path|None>}}
    """
    from datetime import datetime, timezone
    import requests

    out: Dict[str, Dict[str, Optional[str]]] = {}
    os.makedirs(output_path, exist_ok=True)

    def _append_failed(line: str) -> None:
        if not failed_log_path:
            return
        with open(failed_log_path, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")

    def _iso_z_to_dt(s: str) -> datetime:
        # expects "YYYY-MM-DDTHH:MM:SSZ"
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    def _hv_dt_to_dt(s: str) -> datetime:
        # Helioviewer getClosestImage returns "YYYY-MM-DD HH:MM:SS" (UTC)
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    def _get_closest_image_id_and_date(date: str, sid: int, timeout: float = 60.0):
        url = f"https://api.helioviewer.org/v2/getClosestImage/"
        r = requests.get(url, params={"date": date, "sourceId": int(sid)}, timeout=timeout)
        if r.status_code != 200:
            return None, None
        js = r.json()
        return js.get("id"), js.get("date")

    for date in dates:
        header_txt_path: Optional[str] = None
        fits_path: Optional[str] = None

        try:
            image_id, closest_str = _get_closest_image_id_and_date(date, source_id)

            if image_id is None or closest_str is None:
                _append_failed(f"{date}\tsourceId={source_id}\tFAIL:no_closest")
                out[date] = {"header_txt": None, "fits": None}
                continue

            if max_time_delta_seconds is not None:
                try:
                    req_dt = _iso_z_to_dt(date)
                except Exception:
                    _append_failed(f"{date}\tsourceId={source_id}\tFAIL:bad_requested_date_format")
                    out[date] = {"header_txt": None, "fits": None}
                    continue

                try:
                    clo_dt = _hv_dt_to_dt(closest_str)
                except Exception:
                    _append_failed(
                        f"{date}\tsourceId={source_id}\tFAIL:bad_closest_date_format\tclosest={closest_str}"
                    )
                    out[date] = {"header_txt": None, "fits": None}
                    continue

                dt_sec = abs((clo_dt - req_dt).total_seconds())
                if dt_sec > float(max_time_delta_seconds):
                    _append_failed(
                        f"{date}\tsourceId={source_id}\tSKIP:closest_out_of_range\t"
                        f"closest={clo_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}\tdt_sec={int(dt_sec)}"
                    )
                    out[date] = {"header_txt": None, "fits": None}
                    continue

            # fetch payloads
            jp2_bytes = get_jp2_image_bytes(image_id)
            header_text = get_jp2_header_text(image_id)

            if jp2_bytes is None or header_text is None:
                _append_failed(f"{date}\tsourceId={source_id}\tFAIL:download_jp2_or_header\tid={image_id}")
                out[date] = {"header_txt": None, "fits": None}
                continue

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

        except Exception as e:
            _append_failed(f"{date}\tsourceId={source_id}\tFAIL:exception\t{type(e).__name__}: {e}")
            out[date] = {"header_txt": None, "fits": None}

    return out


def _append_failed(path: str, line: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")

