from __future__ import annotations

import os
from typing import Dict, List, Optional, Union

import imageio.v3 as iio
import numpy as np

from .fits import jp2_bytes_to_numpy
from .hv_api import get_closest_image_id, get_jp2_image_bytes


def _to_uint8(img: np.ndarray) -> np.ndarray:
    """Normalize an array to uint8 for PNG output."""
    arr = np.asarray(img)

    if arr.dtype == np.uint8:
        return arr

    arr = arr.astype(np.float64, copy=False)
    mn = np.nanmin(arr)
    mx = np.nanmax(arr)
    if mx == mn:
        return np.zeros(arr.shape, dtype=np.uint8)

    arr = (arr - mn) / (mx - mn)
    return (255.0 * arr).astype(np.uint8)


def save_images_by_date_png(
    dates: List[str],
    source_id: int,
    base_output_path: str = ".",
    max_time_delta_seconds: Optional[float] = None,
    failed_log_path: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Download PNG(s) for each requested date and write to disk under:
        base_output_path/png/YYYY-MM-DD/<stem>_source_<source_id>.png

    New options:
      - max_time_delta_seconds: if set, only download when the Helioviewer "closest image"
        timestamp is within ±max_time_delta_seconds of the requested date.
      - failed_log_path: if set, append skipped/failed requests to this text file.

    Returns
    -------
    dict: {date_str: <png_path|None>}
    """
    from datetime import datetime, timezone
    import os
    import requests

    out: Dict[str, Optional[str]] = {}

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
        url = "https://api.helioviewer.org/v2/getClosestImage/"
        r = requests.get(url, params={"date": date, "sourceId": int(sid)}, timeout=timeout)
        if r.status_code != 200:
            return None, None
        js = r.json()
        return js.get("id"), js.get("date")

    for date in dates:
        png_path: Optional[str] = None

        try:
            image_id, closest_str = _get_closest_image_id_and_date(date, source_id)

            if image_id is None or closest_str is None:
                _append_failed(f"{date}\tsourceId={source_id}\tFAIL:no_closest")
                out[date] = None
                continue

            if max_time_delta_seconds is not None:
                try:
                    req_dt = _iso_z_to_dt(date)
                except Exception:
                    _append_failed(f"{date}\tsourceId={source_id}\tFAIL:bad_requested_date_format")
                    out[date] = None
                    continue

                try:
                    clo_dt = _hv_dt_to_dt(closest_str)
                except Exception:
                    _append_failed(
                        f"{date}\tsourceId={source_id}\tFAIL:bad_closest_date_format\tclosest={closest_str}"
                    )
                    out[date] = None
                    continue

                dt_sec = abs((clo_dt - req_dt).total_seconds())
                if dt_sec > float(max_time_delta_seconds):
                    _append_failed(
                        f"{date}\tsourceId={source_id}\tSKIP:closest_out_of_range(PNG)\t"
                        f"closest={clo_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}\tdt_sec={int(dt_sec)}"
                    )
                    out[date] = None
                    continue

            # Build output path: base_output_path/png/YYYY-MM-DD/
            day = date.split("T", 1)[0]
            day_dir = os.path.join(base_output_path, "png", day)
            os.makedirs(day_dir, exist_ok=True)

            stem = date.replace(":", "").replace("T", "_")
            png_path = os.path.join(day_dir, f"helioviewer_{stem}_source_{source_id}.png")

            # Download PNG bytes from Helioviewer (client uses getJPEG but we want PNG)
            # If your existing package already has a helper like get_png_image_bytes(image_id),
            # replace the request below with that helper to keep everything consistent.
            url = "https://api.helioviewer.org/v2/getPNG/"
            r = requests.get(url, params={"id": int(image_id)}, timeout=120)
            if r.status_code != 200:
                _append_failed(f"{date}\tsourceId={source_id}\tFAIL:download_png\tid={image_id}\tstatus={r.status_code}")
                out[date] = None
                continue

            with open(png_path, "wb") as f:
                f.write(r.content)

            out[date] = png_path

        except Exception as e:
            _append_failed(f"{date}\tsourceId={source_id}\tFAIL:exception(PNG)\t{type(e).__name__}: {e}")
            out[date] = None

    return out


def _append_failed(path: str, line: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")

