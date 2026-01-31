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
    dates: Union[str, List[str]],
    source_id: int,
    base_output_path: str = ".",
    filename: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Download JP2 and save a PNG into YYYY-MM-DD folders.

    Parameters
    ----------
    dates
        A single ISO8601 date string or a list of them.
    source_id
        Helioviewer sourceId.
    base_output_path
        Root output directory.
    filename
        If provided, uses this filename within each date folder.
        Otherwise defaults to "helioviewer_{source_id}.png".

    Returns
    -------
    dict
        {date: png_path or None}
    """
    if isinstance(dates, str):
        dates = [dates]

    out: Dict[str, Optional[str]] = {}

    for date in dates:
        image_id = get_closest_image_id(date, source_id)
        if image_id is None:
            out[date] = None
            continue

        jp2_bytes = get_jp2_image_bytes(image_id)
        if jp2_bytes is None:
            out[date] = None
            continue

        img = jp2_bytes_to_numpy(jp2_bytes)
        png_img = _to_uint8(img)

        date_folder = date.split("T")[0]
        folder = os.path.join(base_output_path, date_folder)
        os.makedirs(folder, exist_ok=True)

        out_name = filename or f"helioviewer_{source_id}.png"
        path = os.path.join(folder, out_name)
        iio.imwrite(path, png_img, extension=".png")
        out[date] = path

    return out
